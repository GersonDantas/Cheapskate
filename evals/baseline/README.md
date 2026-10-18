# Evaluation baseline

These files capture commit `17a903e` immediately before the RTK, Caveman,
CodeGraph, and Graphify policies were added to the repository candidate.

The baseline answers a narrow question: how do the additional shared policies
affect instruction size and model behavior? It does not represent the older,
verbose pre-reduction instructions and does not measure hooks, terminal output,
graph indexes, end-to-end token savings, or billing.

Keep these fixtures immutable. A different experimental question requires a new
named baseline rather than rewriting this directory.
