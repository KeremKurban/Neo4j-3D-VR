from flask import Flask, jsonify, render_template, request
from neo4j import GraphDatabase
import time

app = Flask(__name__, static_folder='../../../static', template_folder='../../../templates')

# Neo4j connection details
uri = "bolt://localhost:7687"
username = "neo4j"
password = "password"

driver = GraphDatabase.driver(uri, auth=(username, password))

def get_nodes_and_links(tx, limit=100):
    nodes = []
    links = []

    # Query to get limited nodes with all properties
    result = tx.run(f"""
        MATCH (n:Paper)
        RETURN n
        LIMIT {limit}
    """)
    for record in result:
        node = record["n"]
        node_data = {
            "uid": node["uid"],
            "label": node["title"] if "title" in node else node.id,
            "is_bbp": node.get("is_bbp", False),
        }
        nodes.append(node_data)

    # Collect node UIDs
    node_uids = [node["uid"] for node in nodes]

    # Query to get relationships between the limited nodes
    result = tx.run(f"""
        MATCH (n:Paper)-[r:CITES]->(m:Paper)
        WHERE n.uid IN {node_uids} AND m.uid IN {node_uids}
        RETURN n.uid AS source, m.uid AS target, r
    """)
    for record in result:
        link_data = {
            "source": record["source"],
            "target": record["target"],
        }
        links.append(link_data)

    return nodes, links

def with_retry(session_func, *args, retries=5, delay=1):
    for attempt in range(retries):
        try:
            with driver.session() as session:
                return session_func(session, *args)
        except InterruptedError:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            else:
                raise

@app.route('/nodes')
def get_nodes():
    limit = int(request.args.get('limit', 100))  # Get limit from query parameter or default to 100
    nodes, _ = with_retry(lambda s: s.read_transaction(get_nodes_and_links, limit))
    return jsonify(nodes)

@app.route('/links')
def get_links():
    limit = int(request.args.get('limit', 100))  # Get limit from query parameter or default to 100
    _, links = with_retry(lambda s: s.read_transaction(get_nodes_and_links, limit))
    return jsonify(links)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)