# Integration in LIIT

Die neue Fassung ist ein eigenständiges Paket. Kern und Module der ersten Lieferung behalten ihre bisherigen Versions- und Integritätsnachweise. Die neun Module werden hier als unveränderte Quelldateien mitgeliefert; eine ausdrückliche Bindungsdatei je Modul erlaubt ihre Interpretation durch den Kern 2.0.0. Ihre Aussagen wurden nicht stillschweigend umgeschrieben.

## Zuständigkeiten

| Bestandteil | Inhalt |
|---|---|
| core.v2.0.0.json | Acht Prüfschritte, Zustände, Teilprüfung und Ergebnisvertrag |
| dialogue_guidance.v1.0.0.json | Gesprächsregeln und Fragen |
| legacy_modules und bindings | Neun ursprüngliche Module und ausdrückliche Bindung an den neuen Kern |
| schemas | Eingangs- und Ausgangsverträge |
| runtime | Referenzauswertung dokumentierter Merkmale und Ausgabe konkreter Felder |
| interfaces | Bestehende Dienstverträge und laufende Übergabe |

## Neuer Fallvertrag

Pro Fall werden Beteiligte, Anliegen, Rechte und Pflichten, Ereignisse, ausgewählte Rechtsbehelfe und Verfahrensprüfungen dokumentiert. Leere Listen sind während einer Teilprüfung zulässig und erscheinen als unvollständige Arbeitsstufe. Es darf keine implizite vollständige Fallprüfung behauptet werden.

Jede atomare Bewertung referenziert die Tatsachen, auf denen sie beruht, mit deren Revision. Das ist eine Referenz für die Argumentation, kein Ersatz für die Beurteilung der Beweisqualität. Wenn eine Tatsachenrevision nicht mehr passt, behandelt die Auswertung diese Bewertung als unknown.

Anwendbarkeit wird in context_checks erfasst. In den mitgelieferten Bindungen gelten scope und temporal konservativ für alle rechtlichen Ergebnisse. Bei unbekanntem Kontext werden verfügbare Einzelbewertungen und offene Fragen trotzdem ausgegeben. Eine positive Regelverknüpfung erscheint dann nur als hypothetical_effect mit ausdrücklich genannten offenen Voraussetzungen. Ein sicher ausgeschlossener Kontext erzeugt not_applicable ohne solche Rechtsfolge.

## Konkrete Rechtsfolgen

Für jedes Ergebnis können berechtigte und verpflichtete Person, Handlung, Betrag/Umfang, Beginn, Ende, Mietvertragswirkung, Konkurrenz zu anderen Rechtsbehelfen und weitere Voraussetzungen belegt werden. Jede Angabe enthält status, value und evidence_refs. Nicht belegte oder fehlende Angaben bleiben unknown. Der allgemeine Modultext wird als rule_effect geführt und ersetzt keine individuelle Konkretisierung.

Die Referenz erzeugt aus einem positiven Tatbestand keine automatisch versandten Schreiben, keine Fristenden und keine Lane. Tatsächliche Dienstantworten sind gesondert zu übernehmen.

## Technische Einbindung

1. Hashwerte gegen ein extern gepinntes Manifest prüfen.
2. Kern, Modul und dessen passende Bindung laden.
3. Fall anhand schemas/case.schema.json validieren und Tatsachen-/Belegreferenzen auflösen.
4. Rechte und Pflichten, Ereignisqualifikation und Auswahl der Rechtsbehelfe begründen; keine automatische juristische Interpretation von Freitext unterstellen.
5. evaluate(module, binding, caseRecord, {core, sourceModuleSha256}) aus runtime/evaluator.mjs aufrufen. Der Hash ist aus den geladenen Quelldateibytes zu ermitteln.
6. Ergebnis gegen schemas/result.schema.json prüfen und anhand der Gesprächsregeln ausgeben.
7. Ereignisse gleichzeitig mit ihrer Erfassung an bestehende Dienste geben. Die Auswertung versendet keine Anfragen.
8. Fallrevision bei Änderungen erhöhen; veraltete Bewertungen erneut prüfen.

Node-Aufruf zur Paketprüfung: node tests/run.mjs. Die Beispiele sind synthetisch und enthalten bereits vorbewertete Merkmale. Der Testbericht belegt Referenzverhalten, keine juristische Fachfreigabe oder produktive Installation.
