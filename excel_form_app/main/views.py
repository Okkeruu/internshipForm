from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
import pandas as pd
from .forms import UploadExcelForm, CustomUserCreationForm, PersonForm
from .models import Person, UploadLog
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView

def home(request):
    return render(request, 'home.html')

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

def clean(value):
    if pd.isna(value):
        return None
    return str(value).strip()
    
def clean_ari8mos(value):
    if pd.isna(value):
        return None
   
    try:
        return str(int(value))  # 115011.0 → "115011"
    except (ValueError, TypeError):
        return str(value).strip() 

@login_required
def show_people(request):
    people = Person.objects.all()
    return render(request, 'main/people.html', {'people': people})

@login_required
def upload_excel(request):
    if request.method == 'POST':
        form = UploadExcelForm(request.POST, request.FILES)

        if form.is_valid():
            excel_file = request.FILES['excel_file']
            df = pd.read_excel(excel_file)
            
            existing_ids = set(
            Person.objects.values_list('ari8mosEisagoghs', flat=True)
            )

            added = []
            skipped = []
            duplicates = []
            new_objects = []

            for index, row in df.iterrows():
                ari8mos = clean_ari8mos(row.get('ΑΡΙΘΜΟΣ ΕΙΣΑΓΩΓΗΣ'))


                if not ari8mos:
                    skipped.append({
                        'row': index + 2,
                        'reason': 'Missing ΑΡΙΘΜΟΣ ΕΙΣΑΓΩΓΗΣ'
                    })
                    continue

                # 🔴 DUPLICATE CHECK (ONLY ari8mos)
                if ari8mos in existing_ids:
                   existing_person = Person.objects.get(ari8mosEisagoghs=ari8mos)

                   duplicates.append({
                     "left": {
                        "ari8mos": existing_person.ari8mosEisagoghs,
                        "titlos": existing_person.titlos,
                        "syggrafeas": existing_person.syggrafeas,
                        "ekdoths": existing_person.ekdoths,
                     },
                      "right": {
                         "ari8mos": ari8mos,
                         "titlos": clean(row.get('ΤΙΤΛΟΣ')),
                         "syggrafeas": clean(row.get('ΣΥΓΓΡΑΦΕΑΣ')),
                         "ekdoths": clean(row.get('ΕΚΔΟΤΗΣ')),
                     },
             #"row": index + 2,
                  })
                   continue

                # ✅ SAFE INSERT
                new_objects.append( Person(
                    ari8mosEisagoghs=ari8mos,
                    hmeromhnia_eis=clean(row.get('ΗΜΕΡΟΜΗΝΙΑ ΕΙΣΑΓΩΓΗΣ')),
                    syggrafeas=clean(row.get('ΣΥΓΓΡΑΦΕΑΣ')),
                    koha=clean(row.get('ΣΥΓΓΡΑΦΕΑΣ KOHA')),
                    titlos=clean(row.get('ΤΙΤΛΟΣ')),
                    ekdoths=clean(row.get('ΕΚΔΟΤΗΣ')),
                    ekdosh=clean(row.get('ΕΚΔΟΣΗ')),
                    etosEkdoshs=clean(row.get('ΕΤΟΣ ΕΚΔΟΣΗΣ')),
                    toposEkdoshs=clean(row.get('ΤΟΠΟΣ  ΕΚΔΟΣΗΣ')),
                    sxhma=clean(row.get('ΣΧΗΜΑ')),
                    selides=clean(row.get('ΣΕΛΙΔΕΣ')),
                    tomos=clean(row.get('ΤΟΜΟΣ')),
                    troposPromPar=clean(row.get('ΤΡΟΠΟΣ ΠΡΟΜΗΘΕΙΑΣ ΠΑΡΑΤΗΡΗΣΕΙΣ')),
                    ISBN=clean(row.get('ISBN')),
                    sthlh1=clean(row.get('Στήλη1')),
                    sthlh2=clean(row.get('Στήλη2')),
                    )
                )
                existing_ids.add(ari8mos)                      

                added.append({
                    'ari8mos': ari8mos,
                    'titlos': clean(row.get('ΤΙΤΛΟΣ')),
                    'syggrafeas': clean(row.get('ΣΥΓΓΡΑΦΕΑΣ')),
                })
           
            Person.objects.bulk_create(new_objects, batch_size=1000)
           
            # ✅ Store duplicates for next step
            request.session['duplicates'] = duplicates

            # ✅ Log upload
            UploadLog.objects.create(
                user=request.user,
                filename=excel_file.name,
                rows_added=len(new_objects),
                rows_updated=0,
            )

            return render(request, 'upload_result.html', {
                'added_count': len(new_objects),
                'duplicate_count': len(duplicates),
                'skipped_count': len(skipped),
                #'duplicates_preview': duplicates[:50],  # show first 50 only
            })

    else:
        form = UploadExcelForm()

    return render(request, 'upload_excel.html', {'form': form})

@login_required
def resolve_duplicates(request):
    duplicates = request.session.get('duplicates', [])

    if not duplicates:
        return render(
             request,
            'main/duplicates_done.html'  
        )
    
    current = duplicates[0]
    return render(request, 'main/duplicates.html', {'duplicates': duplicates})


@login_required
def handle_duplicate(request):
    if request.method != "POST":
        return redirect('resolve_duplicates')
    
    duplicates = request.session.get('duplicates', [])
    print("BEFORE POP:", len(duplicates))
    
    if not duplicates:
        return redirect('resolve_duplicates')


    dup = duplicates.pop(0)  # ✅ remove from session list
    request.session['duplicates'] = duplicates
    print("AFTER POP:", len(duplicates))

    if request.POST.get('action') == "edit":
      return redirect(f"{reverse('edit_person', args=[dup['left']['ari8mos']])}?next=duplicates")
    
    return redirect('resolve_duplicates')


@login_required
def edit_person(request, pk):
    # Fetch the person by primary key (ari8mosEisagoghs)
    person = get_object_or_404(Person, pk=pk)

    # detect where we came from
    next_url = request.GET.get('next')

    if request.method == 'POST':
        # If you have a form to edit a Person, use it here
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()

            # ✅ confirmation message
            messages.success(request, "Record updated successfully.")

            # ✅ go back to duplicates if needed
            if next_url == 'duplicates':
                return redirect('resolve_duplicates')

            return redirect('show_people')

            #return redirect('show_people')  # or wherever you want to go after edit
    else:
        form = PersonForm(instance=person)

    return render(request, 'main/edit_person.html', {'form': form, 'person': person})