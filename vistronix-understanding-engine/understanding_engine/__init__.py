"""
understanding_engine package
=============================
The AI Document Understanding Engine for VisTronix AI.

This package takes the `parsed_document.json` produced by the PDF Parser
module and runs it through a pipeline of specialized analysis modules to
produce `knowledge_graph.json` - a rich, structured, teacher-quality
understanding of the document's educational content.

See knowledge_graph_builder.py for the pipeline entry point, and main.py
(at the project root) for the FastAPI application that exposes it.
"""
