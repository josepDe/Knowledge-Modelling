from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import Optional, NumberRange
from SPARQLWrapper import SPARQLWrapper, JSON


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SPARQL Endpoint
sparql = SPARQLWrapper("http://localhost:3030/dataset/sparql")

animals = [{"name": "Buddy", "age": 5, "owner": "John Doe", "type": "Dog"}]  # Mock data for animals
appointments = []  # Mock data for appointments

appointments = []  # Mock data for appointments
owners = []

# Flask-WTF Forms
class AnimalSearchForm(FlaskForm):
    microchip_id = StringField('MicrochipId', validators=[Optional()])
    owner = StringField('Owner Name', validators=[Optional()])
    submit = SubmitField('Search')

class AppointmentSearchForm(FlaskForm):
    animal_name = StringField('Animal Name', validators=[Optional()])
    vet_name = StringField('Vet Name', validators=[Optional()])
    owner_name = StringField('Owner Name', validators=[Optional()])
    submit = SubmitField('Search Appointments')

# Routes
@app.route('/', methods=['GET', 'POST'])
@app.route('/search_animal', methods=['GET', 'POST'])
def search_animal():

    sparql = SPARQLWrapper("http://localhost:3030/dataset/sparql")
    form = AnimalSearchForm()
    search_results = []

    if form.validate_on_submit():
        # Get input from the form
        microchip_id = form.microchip_id.data.strip() if form.microchip_id.data else None
        owner_name = form.owner.data.strip() if form.owner.data else None

        if microchip_id and not owner_name:
            sparql_query = f"""PREFIX vc: <http://www.semanticweb.org/j/ontologies/2024/11/Veterinary_Care#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?MicrochipIdId ?animalName ?age ?weight
            WHERE {{
            ?pet a ?subclass .
            ?subclass rdfs:subClassOf vc:NormalPets .
            ?pet vc:MicrochipId "{microchip_id}" .

            # Required details
            ?pet vc:AnimalId ?animalName .
            ?pet vc:Age ?age .
            ?pet vc:MicrochipId ?MicrochipIdId.
            ?pet vc:Weight ?weight.
            }}
            """

        elif owner_name and not microchip_id:
            sparql_query= f"""PREFIX vc: <http://www.semanticweb.org/j/ontologies/2024/11/Veterinary_Care#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?MicrochipIdId ?animalName ?age ?weight
            WHERE {{
                # Match the owner instance by name
                ?owner vc:OwnerName "{owner_name}" .
                
                # Find the pet owned by this owner
                ?owner vc:Owns ?pet .
                
                # Required details
                ?pet vc:AnimalId ?animalName .
                ?pet vc:Age ?age .
                ?pet vc:MicrochipId ?MicrochipIdId.
                ?pet vc:Weight ?weight.
            }}"""

        elif owner_name and microchip_id:
            sparql_query = f"""PREFIX vc: <http://www.semanticweb.org/j/ontologies/2024/11/Veterinary_Care#>

            SELECT ?MicrochipIdId ?animalName ?age ?weight
            WHERE {{
                # Match the owner instance by name
                ?owner vc:OwnerName "{owner_name}" .
                
                # Find the pet owned by this owner
                ?owner vc:Owns ?pet .
                
                # Filter by the pet's MicrochipId
                ?pet vc:MicrochipId "{microchip_id}" .
                
                # Retrieve pet details
                ?pet vc:AnimalId ?animalName .
                ?pet vc:Age ?age .
                ?pet vc:Weight ?weight .
                ?pet vc:MicrochipId ?MicrochipIdId.
            }}
            """

        else:
            sparql_query = None


        sparql.setQuery(sparql_query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        for binding in results['results']['bindings']:
            pet_data = {
                'animalName': binding['animalName']['value'],
                'microchipId': binding['MicrochipIdId']['value'],
                'age': binding['age']['value'],
                'weight':binding['weight']['value'],
                'owner': owner_name  # Add the owner dynamically
            }
            search_results.append(pet_data)

    return render_template(
        'Vetter.html',
        form=form,
        search_results=search_results
    )


@app.route('/add_animal', methods=['POST'])
def add_animal():
    sparql = SPARQLWrapper("http://localhost:3030/dataset/update")
    animal_name = request.form.get('animal_name')
    owner_name = request.form.get('owner_name')
    microchip_id = request.form.get('microchip_id')
    animal_type = request.form.get('animal_type')

    if not animal_name or not owner_name or not microchip_id or not animal_type:
       return " please add all inputs", 200

    sanitized_animal_name = animal_name.replace(' ', '_')
    sanitized_owner_name = owner_name.replace(' ', '_')
    sanitized_animal_type = animal_type.replace(' ', '_')


    sparql_query = f"""
    PREFIX vc: <http://www.semanticweb.org/j/ontologies/2024/11/Veterinary_Care#>

    INSERT {{
        vc:{sanitized_animal_name} a vc:{sanitized_animal_type} ;
                                    vc:AnimalId "{animal_name}" ;
                                    vc:MicrochipId "{microchip_id}" ;
                                    vc:OwnedBy vc:{sanitized_owner_name} .
    }}
    WHERE {{
        FILTER EXISTS {{
            vc:{sanitized_owner_name} a vc:Owner ;
                                       vc:OwnerName "{owner_name}" .
        }}
    }}
    """
    print( sparql_query )
    try:
        sparql.setQuery(sparql_query)
        sparql.method = 'POST'
        sparql.addCustomHttpHeader('Content-Type', 'application/sparql-update')
        sparql.query()
    except Exception as e:
       return "Error: Failed to add animal to the database.", 500
    return "Animal added successfully!", 201

@app.context_processor
def inject_options():
    sparql_query = """
        PREFIX vc: <http://www.semanticweb.org/j/ontologies/2024/11/Veterinary_Care#>        SELECT ?ownerName
        WHERE {
            ?owner a vc:Owner .       # Match all instances of the Owner class
            ?owner vc:OwnerName ?ownerName .  # Retrieve the name of the owner
        }
            """
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    for binding in results['results']['bindings']:
        owners.append( binding["ownerName"]['value'])

    # Provide dynamic options to the template
    return {
        'owners': owners,
        'animal_options': [animal["name"] for animal in animals]
    }

if __name__ == '__main__':
    app.run(debug=True)
