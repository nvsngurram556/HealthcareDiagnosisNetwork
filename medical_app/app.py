# app.py
import flask
from flask import request, jsonify
import networkx as nx
import pandas as pd
import io
import json

# Initialize Flask app
app = flask.Flask(__name__)

# Initialize a directed graph using NetworkX to store medical knowledge
# This graph will persist in memory for the duration of the application.
G = nx.DiGraph()

# Define categories for nodes to help with visualization and clustering
NODE_CATEGORIES = {
    "symptom": "#FFD700",  # Gold
    "disease": "#DC143C",  # Crimson
    "treatment": "#4682B4", # SteelBlue
    "specialist": "#32CD32" # LimeGreen
}

# --- Helper Functions ---

def add_relationship_to_graph(source_entity, relationship_type, target_entity, source_type=None, target_type=None):
    """
    Adds a new relationship (edge) to the knowledge graph.
    Nodes are added if they don't already exist.
    'type' attribute is added to nodes for visualization purposes.
    """
    # Add source node if it doesn't exist, assigning its type
    if source_entity not in G:
        G.add_node(source_entity, type=source_type if source_type else "unknown")
    else:
        # Update type if a more specific type is provided
        if source_type and G.nodes[source_entity].get('type') == "unknown":
            G.nodes[source_entity]['type'] = source_type

    # Add target node if it doesn't exist, assigning its type
    if target_entity not in G:
        G.add_node(target_entity, type=target_type if target_type else "unknown")
    else:
        # Update type if a more specific type is provided
        if target_type and G.nodes[target_entity].get('type') == "unknown":
            G.nodes[target_entity]['type'] = target_type

    # Add the edge with the relationship type
    if not G.has_edge(source_entity, target_entity):
        G.add_edge(source_entity, target_entity, relationship=relationship_type)
    print(f"Added: {source_entity} --({relationship_type})--> {target_entity}")


def get_graph_data_for_d3():
    """
    Converts the NetworkX graph into a JSON format suitable for D3.js visualization.
    Includes node 'type' and 'color' for better rendering.
    """
    nodes = []
    links = []

    # Prepare nodes data
    for node, attributes in G.nodes(data=True):
        node_type = attributes.get('type', 'unknown')
        nodes.append({
            "id": node,
            "name": node,  # Use 'name' for display in D3
            "type": node_type,
            "color": NODE_CATEGORIES.get(node_type, "#808080") # Default to grey if type not found
        })

    # Prepare links data
    for u, v, attributes in G.edges(data=True):
        links.append({
            "source": u,
            "target": v,
            "relationship": attributes.get('relationship', 'connects')
        })

    return {"nodes": nodes, "links": links}

# --- API Endpoints ---

@app.route('/')
def index():
    """
    Serves the main HTML page.
    """
    return flask.send_file('index.html')

@app.route('/add_relationship', methods=['POST'])
def add_relationship():
    """
    API endpoint to add a single medical concept relationship to the graph.
    Expected JSON payload:
    {
        "source_entity": "Fever",
        "relationship_type": "indicates",
        "target_entity": "Influenza",
        "source_type": "symptom",
        "target_type": "disease"
    }
    """
    data = request.json
    source_entity = data.get('source_entity')
    relationship_type = data.get('relationship_type')
    target_entity = data.get('target_entity')
    source_type = data.get('source_type')
    target_type = data.get('target_type')

    if not all([source_entity, relationship_type, target_entity]):
        return jsonify({"status": "error", "message": "Missing required fields."}), 400

    add_relationship_to_graph(source_entity, relationship_type, target_entity, source_type, target_type)
    return jsonify({"status": "success", "message": "Relationship added successfully.", "graph": get_graph_data_for_d3()})

@app.route('/upload_data', methods=['POST'])
def upload_data():
    """
    API endpoint to upload medical knowledge data in JSON or CSV format.
    File should be named 'file'.
    JSON format example:
    [
        {"source_entity": "Headache", "relationship_type": "symptom_of", "target_entity": "Migraine", "source_type": "symptom", "target_type": "disease"},
        {"source_entity": "Migraine", "relationship_type": "treated_by", "target_entity": "Triptans", "source_type": "disease", "target_type": "treatment"}
    ]
    CSV format example (header: source_entity,relationship_type,target_entity,source_type,target_type):
    source_entity,relationship_type,target_entity,source_type,target_type
    Cough,indicates,Bronchitis,symptom,disease
    Bronchitis,treated_by,Antibiotics,disease,treatment
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    if file:
        file_content = file.read().decode('utf-8')
        try:
            if file.filename.endswith('.json'):
                data = json.loads(file_content)
                if not isinstance(data, list):
                    return jsonify({"status": "error", "message": "JSON must be a list of objects"}), 400
            elif file.filename.endswith('.csv'):
                df = pd.read_csv(io.StringIO(file_content))
                data = df.to_dict(orient='records')
            else:
                return jsonify({"status": "error", "message": "Unsupported file type. Only JSON and CSV are supported."}), 400

            for entry in data:
                source_entity = entry.get('source_entity')
                relationship_type = entry.get('relationship_type')
                target_entity = entry.get('target_entity')
                source_type = entry.get('source_type')
                target_type = entry.get('target_type')

                if all([source_entity, relationship_type, target_entity]):
                    add_relationship_to_graph(source_entity, relationship_type, target_entity, source_type, target_type)
                else:
                    print(f"Skipping malformed entry: {entry}")

            return jsonify({"status": "success", "message": "Data uploaded and processed successfully.", "graph": get_graph_data_for_d3()})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/get_graph', methods=['GET'])
def get_graph():
    """
    API endpoint to retrieve the entire current state of the knowledge graph.
    Returns nodes and links suitable for D3.js.
    """
    return jsonify(get_graph_data_for_d3())

@app.route('/query_graph', methods=['POST'])
def query_graph():
    """
    API endpoint to query the knowledge graph based on specific criteria.
    Expected JSON payload:
    {
        "query_type": "diagnoses_for_symptom",
        "entity": "Fever"
    }
    OR
    {
        "query_type": "treatments_for_disease",
        "entity": "Influenza"
    }
    OR
    {
        "query_type": "specialists_for_disease",
        "entity": "Influenza"
    }
    OR
    {
        "query_type": "specialists_for_treatment",
        "entity": "Antivirals"
    }
    """
    data = request.json
    query_type = data.get('query_type')
    entity = data.get('entity')
    results = []
    message = ""

    if not entity:
        return jsonify({"status": "error", "message": "Entity for query is missing."}), 400

    if entity not in G:
        return jsonify({"status": "info", "message": f"'{entity}' not found in the knowledge graph."}), 200

    if query_type == "diagnoses_for_symptom":
        # Find diseases indicated by the symptom
        for neighbor in G.successors(entity):
            if G[entity][neighbor].get('relationship') == "indicates":
                results.append(neighbor)
        message = f"Possible diagnoses for '{entity}': {', '.join(results) if results else 'None found'}"

    elif query_type == "treatments_for_disease":
        # Find treatments for the disease
        for neighbor in G.successors(entity):
            if G[entity][neighbor].get('relationship') == "treated_by":
                results.append(neighbor)
        message = f"Recommended treatments for '{entity}': {', '.join(results) if results else 'None found'}"

    elif query_type == "specialists_for_disease":
        # Find specialists who manage a disease (disease --managed_by--> specialist)
        for successor in G.successors(entity):
            if G[entity][successor].get('relationship') == "managed_by" and G.nodes[successor].get('type') == 'specialist':
                results.append(successor)
        message = f"Specialists associated with '{entity}': {', '.join(results) if results else 'None found'}"

    elif query_type == "specialists_for_treatment":
        # Find specialists who prescribe a treatment (treatment --prescribed_by--> specialist)
        # Note: This implies the relationship is FROM treatment TO specialist.
        # If the relationship is specialist -> prescribes -> treatment, we would look at predecessors.
        for successor in G.successors(entity):
            if G[entity][successor].get('relationship') == "prescribed_by" and G.nodes[successor].get('type') == 'specialist':
                results.append(successor)
        message = f"Specialists who prescribe '{entity}': {', '.join(results) if results else 'None found'}"

    else:
        return jsonify({"status": "error", "message": "Invalid query type."}), 400

    return jsonify({"status": "success", "results": results, "message": message})

# To run the Flask app:
# 1. Save this code as `app.py`.
# 2. Open your terminal, navigate to the directory where you saved `app.py`.
# 3. Run `pip install Flask networkx pandas` if you haven't already.
# 4. Run `flask run`. By default, it will run on http://127.0.0.1:5000/

if __name__ == '__main__':
    # Initial seeding of the graph for demonstration purposes
    # These will be present when the app starts
    add_relationship_to_graph("Fever", "indicates", "Influenza", "symptom", "disease")
    add_relationship_to_graph("Fever", "indicates", "Common Cold", "symptom", "disease")
    add_relationship_to_graph("Influenza", "treated_by", "Antivirals", "disease", "treatment")
    add_relationship_to_graph("Influenza", "managed_by", "Infectious Disease Specialist", "disease", "specialist")
    add_relationship_to_graph("Common Cold", "treated_by", "Rest and Fluids", "disease", "treatment")
    add_relationship_to_graph("Antivirals", "prescribed_by", "Infectious Disease Specialist", "treatment", "specialist")
    add_relationship_to_graph("Headache", "indicates", "Migraine", "symptom", "disease")
    add_relationship_to_graph("Migraine", "treated_by", "Triptans", "disease", "treatment")
    add_relationship_to_graph("Migraine", "managed_by", "Neurologist", "disease", "specialist")
    add_relationship_to_graph("Triptans", "prescribed_by", "Neurologist", "treatment", "specialist")
    add_relationship_to_graph("Shortness of Breath", "indicates", "Asthma", "symptom", "disease")
    add_relationship_to_graph("Asthma", "treated_by", "Inhalers", "disease", "treatment")
    add_relationship_to_graph("Asthma", "managed_by", "Pulmonologist", "disease", "specialist")
    add_relationship_to_graph("Inhalers", "prescribed_by", "Pulmonologist", "treatment", "specialist")
    add_relationship_to_graph("Chest Pain", "indicates", "Heart Attack", "symptom", "disease")
    add_relationship_to_graph("Heart Attack", "treated_by", "Angioplasty", "disease", "treatment")
    add_relationship_to_graph("Heart Attack", "managed_by", "Cardiologist", "disease", "specialist")
    add_relationship_to_graph("Angioplasty", "prescribed_by", "Cardiologist", "treatment", "specialist")

    app.run(debug=True)
