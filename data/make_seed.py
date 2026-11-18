"""Regenerates data/seed/*.jsonl: a small starter dataset compiled from public web pages and news coverage.
The scraper (scraper/scrape.py) adds fresher, fuller data on top of this."""
import json
from pathlib import Path

D = "https://darglobal.co.uk/"
dar = [
 ("DarGlobal company overview", D,
  "DarGlobal (Dar Global PLC) is a London-listed international luxury real estate developer and the international arm of Saudi developer Dar Al Arkan, which set it up in 2017. It focuses on high-end branded residences and mixed-use developments, often with global brands such as the Trump Organization, Aston Martin, Lamborghini, Pagani, Missoni, Elie Saab, W Hotels and Mouawad. Its portfolio includes villas and apartments, co-branded residences and off-plan properties. Projects span the UAE, Oman, Qatar, the UK, Spain and Saudi Arabia, with about US$7.5 billion of projects under development according to company statements reported in the press."),
 ("Trump Tower Jeddah (DarGlobal)", D,
  "Trump Tower Jeddah is DarGlobal's first Trump-branded project in Jeddah, Saudi Arabia, unveiled in December 2024 as a luxury residential tower with high-end apartments. On 26 November 2025 DarGlobal awarded the main works contract to Arabian Construction Company (ACC), after enabling and foundation works were completed; the contract was reported as about SAR 2 billion (roughly US$532 million). Press reports give differing headline project values (US$530 million in some, US$1 billion in others)."),
 ("Trump Plaza Jeddah (DarGlobal)", D,
  "Trump Plaza Jeddah is DarGlobal's second collaboration with the Trump Organization in Jeddah, announced as a plan in September 2025 and launched in January 2026 as an estimated US$1 billion mixed-use development. It is to include executive and premium residences, serviced apartments, Grade-A office space, exclusive townhouses, home offices, retail and curated dining, anchored by a Central Park-inspired green spine."),
 ("DarGlobal in Riyadh and new Saudi land", D,
  "In January 2026 DarGlobal unveiled the first of two Trump-branded projects planned for Riyadh: the Trump International Golf Club in Wadi Safar, covering 2.6 million square metres. DarGlobal also announced Saudi land acquisitions in Jeddah and Riyadh totalling about US$390 million. In November 2026 The National reported a new mixed-use development in Jeddah valued at about SAR 1 billion (US$267 million)."),
 ("DarGlobal Dubai and UAE projects", D,
  "DarGlobal is developing Trump International Hotel & Tower, Dubai, a roughly US$1 billion tower on Sheikh Zayed Road; the enabling works contract was awarded to Edrafor Emirates LLC on 10 December 2025. In the UAE it also launched The Astera (US$238 million) on Al Marjan Island, with Aston Martin-designed interiors and an exclusive Sky Villa (US$11 million) in its 1 of 1 portfolio. Other Aston Martin and W Residences branded projects are in the UAE."),
 ("DarGlobal Oman and Spain projects", D,
  "In Oman, DarGlobal's Aida development in Muscat includes Trump International Oman (resort, golf club and residences), The Great Escape 2 (US$70 million residential complex) and Marriott Residences (US$100 million beachfront). In Spain, Tierra Viva is a collection of 53 villas near Marbella developed with Automobili Lamborghini."),
 ("DarGlobal 2024 launches", D,
  "In January 2025 DarGlobal said it had launched ten luxury projects in 2024 across Saudi Arabia, the UAE, Qatar, Oman and Spain with a combined value above US$1.9 billion, and was planning expansion into the United States in 2025."),
]
W = "https://wasalt.sa/en"
was = [
 ("Wasalt platform overview", W,
  "Wasalt is a Saudi Arabian real estate platform that describes itself as the first AI-powered property platform in the Kingdom, covering residential and commercial properties for sale and rent, off-plan Projects and Daily Rentals. It is a joint venture between Dar Al Arkan and Quara Holding, uses AI technology from propgenius.ai, and lists properties verified through REGA (the Real Estate General Authority). It also supports property auctions in partnership with Infath, and offers an app."),
 ("Villa 435 sqm with 3 apartments, Al Salyhyah, Jeddah", W,
  "Villa for sale in Al Salyhyah, East Jeddah: 435 sqm land, 13 bedrooms, 9+ bathrooms, 3 living rooms, 3 apartments, new (built 2025), north facing on a 15 m street. Price 2,050,000 SAR (about 4,713 SAR per sqm)."),
 ("Villa 270 sqm, Al Nadwah, Riyadh", W,
  "Villa for sale in Al Nadwah, Riyadh: 270 sqm land, 6 bedrooms, 5 bathrooms, 2 living rooms, 2 guest rooms, new (built 2025), west facing on a 15 m street. Price 1,150,000 SAR (about 4,259 SAR per sqm)."),
 ("Villa 450 sqm, Wadi Jalil, Taif", W,
  "Villa for sale in Wadi Jalil, Taif: 450 sqm land, 6 bedrooms, 4 bathrooms, built 2025, west facing on an 18 m street, with garden, mosque nearby, elevator and security system. Price 700,000 SAR (about 1,556 SAR per sqm)."),
 ("Villa 337 sqm, Al Wasam, Riyadh", W,
  "Villa for sale in Al Wasam, Riyadh: 337 sqm land, 4 bedrooms, 3 bathrooms, east facing on a 15 m street, built 2026. Price 1,200,000 SAR (about 3,561 SAR per sqm)."),
 ("Villa 1025 sqm, Al Yasmeen, Riyadh", W,
  "Villa for sale in Al Yasmeen, Riyadh: 1,025 sqm land, west facing on a 14 m street, outdoor pool, elevator, driver room. Price 10,000,000 SAR (about 9,756 SAR per sqm)."),
 ("Villa 360 sqm, Al Yasmeen, Riyadh", W,
  "Villa for sale in Al Yasmeen, Riyadh: 360 sqm land and built-up area, 7 bedrooms, 8 bathrooms, 3 floors, built 2024, west facing on a 15 m street. Price 4,800,000 SAR (about 13,333 SAR per sqm)."),
 ("Villa 545 sqm, Al Wasiliyah, Taif", W,
  "Villa for sale in Al Wasiliyah, Taif: 545 sqm land, 6 bedrooms, 4 bathrooms, new, north-east facing on a 15 m street, with 2 separate entrances. Price 900,000 SAR (about 1,651 SAR per sqm)."),
 ("Villa 290 sqm, As Salhiyah, Jeddah", W,
  "Villa for sale in As Salhiyah, East Jeddah: 290 sqm land, 9 bedrooms, west facing on a 16 m street. Price 1,050,000 SAR (about 3,621 SAR per sqm)."),
 ("Land 900 sqm, Al Wafa, Jeddah", W,
  "Residential land for sale in Al Wafa, East Jeddah: 900 sqm, south facing on a 25 m street, with electricity and water connections. Price 900,000 SAR (about 1,000 SAR per sqm), listed as 16.3% below the average price in the Al Wafa area."),
 ("Rest house 300 sqm, Al-Misfah, Riyadh", W,
  "Rest house for sale in Al-Misfah, Riyadh: 300 sqm, 3 bedrooms, 1 year old, north facing on a 15 m street. Price 600,000 SAR (about 2,000 SAR per sqm)."),
 ("Villa 700 sqm, West Naseem, Riyadh", W,
  "Villa for sale in West Naseem, Riyadh: 700 sqm land, 6 bedrooms, built 2014, north facing on a 20 m street. Price 2,800,000 SAR (about 4,000 SAR per sqm)."),
 ("Villa 500 sqm, Az-Zahra, Riyadh", W,
  "Villa for sale in Az-Zahra, Riyadh: 500 sqm land, 6 bedrooms, 2 years old, east facing on a 15 m street. Price 2,500,000 SAR (about 5,000 SAR per sqm)."),
]
out = Path(__file__).parent / "seed"
for name, rows in (("darglobal", dar), ("wasalt", was)):
    with (out / f"{name}_seed.jsonl").open("w", encoding="utf-8") as f:
        for title, url, text in rows:
            f.write(json.dumps({"site": name, "url": url, "title": title, "text": text}, ensure_ascii=False) + "\n")
print("seed written")
