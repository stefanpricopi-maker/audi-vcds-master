## P0101 / MAF — cum îl testezi cu VCDS (TDI)

### Ce urmărești
- VCDS → Engine → Measuring Blocks → **Group 003** (MAF).
- Compară **specified** vs **actual** în log.

### Heuristici utile (orientativ)
- Un MAF defect poate raporta valori “înghețate” (static) sau foarte mici.
- Un MAF sănătos poate raporta peste ~1000 mg/str la “full power” (în funcție de motor/condiții).

### De reținut
P0101 nu înseamnă mereu “MAF e mort”: poate fi fals aer după MAF, restricții admisie/evacuare, sau probleme care afectează încărcarea.

### Surse (public)
- Ghid VCDS Group 003 și interpretare: `https://help.idparts.com/help/testing-for-a-faulty-maf-w-vcds-on-a-tdi`

