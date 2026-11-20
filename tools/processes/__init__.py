"""Graph-interne Read-Write-Prozesse (D48): Sherlock, Watson, Guardian.

Projektneutral (Engine-Schicht; wandert mit NUPORE). Sie LESEN den Graphen und
schreiben (spaeter) angereicherte Knoten zurueck -- sie sind KEINE externen
Engine-Konsumenten (Korrektur D48). v0: lesende Planung/Berichte mit klar
getrennten I/O-Grenzen (Websuche fuer Sherlock, Zustellung fuer Guardian).
"""
