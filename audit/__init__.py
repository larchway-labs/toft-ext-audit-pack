"""Shared registry loading for the Audit Pack.

The extension and the toftaudit CLI read the SAME three files in data/ — the NIST
catalog, the mapping and the evidence registry. That is deliberate and it is the
one structural guarantee this project makes: the control narrative and the
evidence collector cannot disagree about what the controls are, because there is
only one statement of them.
"""
