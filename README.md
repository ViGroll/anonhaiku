# Anonhaiku v0.7 — Online-ready

Website: **Anonhaiku**. Twee publicaties per dag om **06:00 en 18:00 vaste UTC+1**, overeenkomend met **05:00 en 17:00 UTC**, onafhankelijk van zomertijd. GitHub Actions scant elk uur om minuut 23 UTC; updates kunnen vertraagd zijn. De drie selectieklassen zijn *vulgar → poetic → unexpected*, maar staan nergens op de website.

## Eerst lokaal testen (Windows)

1. Pak de ZIP uit in een nieuwe map. Bewaar de oude v0.6-map als backup.
2. Open deze map in Verkenner en typ `cmd` in de adresbalk.
3. `py -m pip install -r requirements.txt`
4. `py -m unittest -q`
5. `py publisher.py --scan --threads 20`
6. Open `docs\index.html` in de browser.

De meegeleverde `haikus.sqlite3` is **leeg**: bewust geen persoonlijke geschiedenis, oude comments of verzonnen voorbeelden in een publieke GitHub-repository. Wie toch een bestaande database wil overnemen, doet dat lokaal na controle. Let op: bij uploaden naar GitHub is de inhoud publiek zichtbaar, ook alle kandidaten in het databasebestand.

## Anoniem/pseudoniem publiceren — eerst goed lezen

- Maak een **apart GitHub-account** met een pseudoniem en apart e-mailadres. Gebruik niet je bestaande GitHub-account, echte naam, herkenbare profielfoto, gekoppelde sociale profielen of persoonlijke commits.
- Zet je publieke GitHub-profielnaam op je pseudoniem en zet je e-mailadres op privé in GitHub-instellingen. Gebruik GitHubs `noreply`-adres voor toekomstige commits. In dit pakket worden automatische commits door `github-actions[bot]` gemaakt.
- Alle bestanden in een **publieke repository** zijn openbaar, waaronder de broncode, de database, de Actions-logs en de publieke accountnaam. GitHub kan technische/accountgegevens kennen. **Geen garantie op volledige anonimiteit**.
- De gepubliceerde pagina bevat geen persoonlijke informatie, trackers of externe fonts; elke haiku bevat wel een bronlink naar /b/.
- Zet voor de lancering geen extra Analytics, formulieren of betaalde domeinnaam aan.

## Publiceren via GitHub (zonder command-line Git)

1. Maak op [github.com](https://github.com) het losse pseudonieme account.
2. Maak een **public** repository `anonhaiku` zonder automatisch README, .gitignore of licentie toe te voegen (deze zitten in het ZIP).
3. Op de repositorypagina: **Add file → Upload files**. Upload alle losse bestanden uit de uitgepakte map, inclusief `.github/workflows/anonhaiku.yml`. Windows houdt `.github` soms verborgen; **de mapstructuur moet exact behouden blijven**. Voor complexe mapupload is GitHub Desktop makkelijker; controleer na afloop op GitHub dat het workflowbestand zichtbaar is.
4. **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**. Sommige accounts beperken deze optie.
5. **Settings → Pages → Build and deployment → Source → GitHub Actions**.
6. **Actions → Anonhaiku — scan and publish → Run workflow** voor de eerste publicatie. Kijk of de workflow groen eindigt.
7. Je site is dan zichtbaar op `https://PSEUDONIEM.github.io/anonhaiku/`. De naam van je account verschijnt dus in de URL; gebruik uitsluitend een pseudoniem.

Automatisch werkt zonder eigen computer, maar GitHub Actions-werkstromen kunnen vertragen of uitvallen. Bij geen kandidaat of netwerkstoring blijft de vorige haiku staan. GitHub kan geautomatiseerde workflows in inactieve publieke repositories na 60 dagen uitschakelen. Controleer geregeld de Actions-pagina.

## Veiligheidsgrenzen

Dit is een automatisch experiment dat onvoorspelbare /b/-tekst ophaalt. De filters zijn beperkt en **geen robuuste moderatie**. Haatdragende, intimiderende, expliciete of privacy-schendende tekst kan door de filters komen. Het is verstandig om vóór brede promotie sterkere inhoudscontrole toe te voegen. Upload geen persoonlijke databases of geheimen. 4chan vereist bronvermelding/links en respect voor API-limieten; beide zijn onderdeel van dit prototype.

## Bestanden

- `scanner.py` — haalt threads op en herkent 5-7-5
- `quality.py` — structurele beoordeling
- `publisher.py` — selectie en publicatie per tijdslot
- `haikus.sqlite3` — initieel lege database die later door de workflow wordt gevuld
- `docs/` — webpagina's; gegenereerd door publisher
- `.github/workflows/anonhaiku.yml` — elk uur scannen, website naar GitHub Pages
