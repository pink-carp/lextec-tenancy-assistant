# LIIT Prüfungskern 2.0.0

Die bisherige Legal Reasoning Guidance ist in eine gemeinsame Prüfmethode integriert. Zwei ausdrücklich neue Prüfschritte erfassen die massgeblichen Rechte und Pflichten sowie das rechtserhebliche Ereignis. Die Ergebnisstruktur beantwortet, wer was ab wann und wie lange verlangen kann. Offene Vorfragen blockieren nur die unbedingte Anwendung betroffener Regeln; Teilbefunde bleiben sichtbar.

- [Prüfungskern lesen](PRUEFUNGSKERN.md)
- [Maschinenlesbarer Kern](core.v2.0.0.json)
- [Anleitung für die Gesprächsführung](BOT_GUIDANCE.md)
- [Integrationszuordnung](integration_map.json)
- [Migration und Einbindung](MIGRATION.md)
- [Eingangsschema](schemas/case.schema.json) und [Ergebnisschema](schemas/result.schema.json)
- [Prüfbericht](tests/report.json)

Die neun ursprünglichen Module sind als legacy_modules beigefügt und werden über bindings ausdrücklich angebunden. Fristenrechner und Eskalation bleiben externe Dienste. Diese Lieferung enthält Spezifikation und getestete Referenzauswertung; die produktive LIIT-Anwendung wurde nicht verändert.

Version 2.0.0 · erstellt am 8. November 2026 · Status integration_reference. Die materiellen Module behalten ihren bisherigen Recherche- und Freigabestatus.
