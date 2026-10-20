"""Inspiration bank: real-world phenomena with the abstract dynamics they contribute to a universe.
Each entry: (name, field, [dynamic tags], [motif words], true one-line fact)."""
import hashlib, random, re

BANK = [
    ("tidal locking", "physics", ["resonance", "oscillation"], ["tide", "lock", "moon"], "A moon that is tidally locked always shows the same face to its planet."),
    ("mycorrhizal networks", "biology", ["symbiosis", "network"], ["root", "thread", "loam"], "Fungal networks link tree roots and move sugars and nutrients between plants."),
    ("the Antikythera mechanism", "history", ["signal", "oscillation"], ["gear", "bronze", "eclipse"], "A geared device from ancient Greece modelled the motions of the sun, moon and eclipses."),
    ("plate tectonics", "geology", ["tipping", "erosion"], ["fault", "basalt", "drift"], "Earth's crust moves in plates whose slow collisions build mountains and trigger earthquakes."),
    ("quorum sensing", "biology", ["signal", "tipping"], ["chorus", "swarm", "threshold"], "Bacteria release signal molecules and change behavior once their population crosses a threshold."),
    ("the Silk Road", "history", ["migration", "network"], ["caravan", "silk", "oasis"], "Overland trade routes connected China with the Mediterranean for over a thousand years."),
    ("entropy", "physics", ["entropy", "diffusion"], ["ash", "heat", "dust"], "In an isolated system, total entropy does not decrease."),
    ("predator-prey cycles", "ecology", ["predation", "oscillation"], ["hunt", "hare", "lynx"], "Predator and prey populations often rise and fall in lagged cycles."),
    ("coral reef bleaching", "ecology", ["tipping", "symbiosis"], ["reef", "bloom", "pallor"], "Corals expel their symbiotic algae under heat stress, turning white."),
    ("the printing press", "technology", ["signal", "diffusion"], ["type", "ink", "folio"], "Movable-type printing in 15th-century Europe sharply lowered the cost of books."),
    ("continental drift", "geology", ["migration", "erosion"], ["shelf", "rift", "pangaea"], "The continents have moved over geological time and once formed a single landmass."),
    ("Lotka-Volterra equations", "mathematics", ["predation", "feedback"], ["ratio", "spiral", "cycle"], "Two coupled differential equations describe predator and prey populations."),
    ("the Roman aqueducts", "history", ["network", "scarcity"], ["arch", "channel", "cistern"], "Roman aqueducts carried water by gravity over long distances to cities."),
    ("black holes", "physics", ["entropy", "tipping"], ["horizon", "void", "lens"], "Nothing that crosses a black hole's event horizon can escape it."),
    ("ant colony foraging", "biology", ["feedback", "network"], ["trail", "pheromone", "mound"], "Ants reinforce short routes to food by laying and following chemical trails."),
    ("the Rosetta Stone", "history", ["signal", "diffusion"], ["glyph", "stele", "cipher"], "One inscription in three scripts let scholars decipher Egyptian hieroglyphs."),
    ("natural selection", "biology", ["selection", "feedback"], ["lineage", "variant", "niche"], "Heritable traits that raise survival and reproduction become more common over generations."),
    ("the Dust Bowl", "history", ["erosion", "scarcity"], ["dune", "drought", "furrow"], "Drought and plowing of prairie grass in the 1930s caused huge dust storms in North America."),
    ("superconductivity", "physics", ["tipping", "resonance"], ["frost", "flux", "coil"], "Some materials lose all electrical resistance below a critical temperature."),
    ("bird migration", "ecology", ["migration", "signal"], ["flock", "meridian", "nest"], "Many birds travel thousands of kilometers between breeding and wintering grounds."),
    ("the Haber-Bosch process", "technology", ["scarcity", "diffusion"], ["nitrate", "furnace", "grain"], "Synthesizing ammonia from air made artificial fertilizer possible at industrial scale."),
    ("Easter Island's deforestation", "history", ["scarcity", "feedback"], ["statue", "grove", "timber"], "Rapa Nui lost most of its palm forest, a contested but widely discussed case of resource depletion."),
    ("bioluminescence", "biology", ["signal", "predation"], ["glow", "abyss", "lure"], "Many deep-sea animals make their own light to lure prey or confuse predators."),
    ("Venice's lagoon canals", "history", ["network", "erosion"], ["lagoon", "pile", "gondola"], "Venice is built on wooden piles in a lagoon and floods during high tides."),
    ("phase transitions", "physics", ["tipping", "diffusion"], ["thaw", "boil", "crystal"], "Matter changes abruptly between solid, liquid and gas at critical temperatures and pressures."),
    ("honeybee waggle dance", "biology", ["signal", "network"], ["comb", "dance", "nectar"], "Foraging bees communicate food direction and distance by dancing in the hive."),
    ("the Great Oxidation Event", "geology", ["tipping", "selection"], ["rust", "breath", "stromatolite"], "About 2.4 billion years ago photosynthesis raised atmospheric oxygen, transforming life."),
    ("radio astronomy", "astronomy", ["signal", "resonance"], ["static", "dish", "pulsar"], "Pulsars are rotating neutron stars that emit regular pulses detected by radio telescopes."),
    ("the Bronze Age collapse", "history", ["tipping", "network"], ["tin", "sea-people", "palace"], "Around 1200 BCE many Mediterranean civilizations declined within a few decades."),
    ("convection cells", "physics", ["oscillation", "diffusion"], ["plume", "mantle", "rise"], "Heated fluid rises and cooler fluid sinks, forming circulating cells."),
    ("lichen symbiosis", "biology", ["symbiosis", "scarcity"], ["crust", "rock", "frond"], "A lichen is a partnership between a fungus and an alga or cyanobacterium."),
    ("the telegraph", "technology", ["signal", "network"], ["wire", "relay", "code"], "Electric telegraphs in the 19th century sent messages across continents in minutes."),
    ("glacial cycles", "climate", ["oscillation", "erosion"], ["ice", "moraine", "epoch"], "Earth has repeatedly alternated between glacial and warmer interglacial periods."),
    ("the Voynich-style undeciphered scripts", "history", ["signal", "scarcity"], ["vellum", "cipher", "herbal"], "Some historical manuscripts remain undeciphered despite long study."),
    ("fractal coastlines", "mathematics", ["erosion", "diffusion"], ["inlet", "scale", "tide"], "A coastline's measured length depends on the ruler used, a hallmark of fractal geometry."),
    ("the immune system", "biology", ["selection", "predation"], ["antibody", "memory", "sentinel"], "Adaptive immunity selects lymphocytes that recognize pathogens and remembers them."),
    ("cloud formation", "climate", ["feedback", "tipping"], ["thunder", "vapor", "front"], "Clouds form when water vapor condenses on tiny particles in rising air."),
    ("the Library of Alexandria", "history", ["signal", "scarcity"], ["scroll", "lamp", "colonnade"], "A major ancient library collected scrolls from across the Mediterranean world."),
    ("slime mold transport networks", "biology", ["network", "feedback"], ["vein", "ooze", "spore"], "Physarum slime molds grow tube networks that resemble efficient transport systems."),
    ("the Krakatoa eruption of 1883", "geology", ["tipping", "signal"], ["ash-sky", "caldera", "wave"], "The 1883 eruption was heard thousands of kilometers away and cooled global temperatures."),
    ("circadian rhythms", "biology", ["oscillation", "signal"], ["dusk", "clock", "dawn"], "Most organisms keep roughly 24-hour internal rhythms synchronized by light."),
    ("gold rushes", "history", ["migration", "scarcity"], ["claim", "sluice", "boomtown"], "Discoveries of gold in the 19th century drew hundreds of thousands of migrants."),
    ("neural networks of the brain", "biology", ["network", "selection"], ["synapse", "spark", "cortex"], "Synapses strengthen with use, a basis for learning in animal brains."),
    ("the Hanseatic League", "history", ["network", "migration"], ["cog", "kontor", "salt"], "A medieval commercial alliance of northern European trading cities."),
    ("resonance bridges", "physics", ["resonance", "feedback"], ["span", "cable", "sway"], "Structures can oscillate strongly when driven near their natural frequency."),
    ("seed dispersal", "ecology", ["diffusion", "migration"], ["drift-seed", "burr", "gust"], "Plants spread seeds using wind, water and animals."),
    ("tardigrades", "biology", ["selection", "scarcity"], ["bearskin", "tun", "dry"], "Tardigrades survive extreme dehydration by entering a dormant state."),
    ("the invention of the mechanical clock", "technology", ["oscillation", "signal"], ["escapement", "bell", "tower"], "Escapement mechanisms in medieval Europe regulated clockwork."),
    ("nitrogen-fixing root nodules", "biology", ["symbiosis", "scarcity"], ["nodule", "legume", "fallow"], "Legumes host bacteria in root nodules that convert atmospheric nitrogen into usable form."),
    ("the Black Death", "history", ["contagion", "network", "tipping"], ["bubo", "flea", "cart"], "The Black Death of the mid-14th century killed a large fraction of Europe's population and spread along trade routes.", ["plague", "pestilence", "death"]),
    ("quarantine", "public health", ["quarantine", "network"], ["lazaret", "forty-days", "harbor"], "The word quarantine comes from the Italian 'quaranta giorni', forty days, the period ships were held in isolation in medieval ports.", ["plague", "isolation", "cordon"]),
    ("John Snow's cholera map", "medicine", ["contagion", "signal"], ["pump", "ward", "ledger"], "In 1854 John Snow mapped London cholera deaths around the Broad Street pump, helping show that the disease spread through water.", ["plague", "epidemic", "cholera"]),
    ("the SIR epidemic model", "mathematics", ["contagion", "tipping"], ["threshold", "susceptible", "burnout"], "Kermack and McKendrick's 1927 model splits a population into susceptible, infected and recovered groups; an outbreak grows only if each case infects more than one other on average.", ["plague", "epidemic", "contagion"]),
    ("smallpox eradication", "medicine", ["contagion", "purge"], ["ring", "lancet", "last-case"], "Smallpox was declared eradicated in 1980 after a global campaign of surveillance and ring vaccination.", ["plague", "eradicate", "purge"]),
    ("forest fire ecology", "ecology", ["purge", "selection"], ["char", "cone", "burn-ground"], "Some forests and their species depend on periodic fire to clear undergrowth and release seeds.", ["purge", "fire", "burn", "cleanse"]),
    ("the Great Fire of London", "history", ["purge", "erosion"], ["ember", "lane", "ruin"], "The 1666 fire destroyed much of the City of London, a year after a major plague outbreak there.", ["purge", "fire", "plague"]),
    ("apoptosis", "cell biology", ["purge", "selection"], ["shed", "cell-song", "fragment"], "Cells can trigger their own orderly death, called apoptosis, which removes damaged or unneeded cells.", ["purge", "cleanse", "death"]),
    ("herd immunity", "medicine", ["contagion", "network", "tipping"], ["shield", "crowd", "gap"], "When enough of a population is immune, an infection struggles to spread, indirectly protecting those who are not immune.", ["plague", "epidemic", "immunity"]),
    ("the Plague of Justinian", "history", ["contagion", "network"], ["granary", "tithe", "omen"], "A major plague pandemic struck the Byzantine Empire in the 6th century CE.", ["plague", "pestilence"]),
    ("humoral medicine and purging", "history", ["purge", "selection"], ["basin", "humor", "lancet-blue"], "Historic European medicine often tried to restore the body's balance by purging and bloodletting, practices now known to be ineffective or harmful.", ["purge", "cleanse", "plague"]),
    ("water balloon fights", "recreation", ["projectile", "splash", "team"], ["balloon", "puddle", "soak"], "A water balloon bursts on impact when its thin rubber skin is stretched past its limit.", ["water", "balloon", "splash", "fight", "soak", "waterballoon"]),
    ("volleyball", "sport", ["rally", "team", "oscillation"], ["net", "spike", "sandline"], "Volleyball was invented in 1895 by William G. Morgan in Holyoke, Massachusetts.", ["volleyball", "volley", "beach", "rally", "spike"]),
    ("projectile motion", "physics", ["projectile", "tipping"], ["arc", "apex", "range"], "Galileo showed that a projectile follows a parabola because its horizontal motion is steady while gravity accelerates it downward.", ["balloon", "throw", "arc", "projectile", "toss"]),
    ("surface tension", "chemistry", ["splash", "diffusion"], ["bead", "skin", "meniscus"], "Surface tension lets water form beads and lets some insects walk on a pond's surface.", ["water", "splash", "drop"]),
    ("the water cycle", "climate", ["diffusion", "oscillation"], ["vapor", "cloud", "downpour"], "Water evaporates, condenses into clouds and falls again as precipitation in a continuous cycle.", ["water", "rain", "cycle"]),
    ("beach dune formation", "geology", ["migration", "erosion"], ["dune", "grain", "crest"], "Wind moves sand grains by hopping and rolling them, building dunes that slowly migrate.", ["beach", "sand", "dune"]),
    ("wave interference", "physics", ["resonance", "splash"], ["trough", "ripple", "swell"], "When two waves meet they add together or cancel, producing patterns of bigger and smaller ripples.", ["water", "wave", "ripple", "splash"]),
    ("rally scoring", "sport", ["rally", "tipping"], ["serve", "point", "side-out"], "Modern volleyball awards a point on every rally, whichever team served.", ["volleyball", "rally", "score"]),
    ("tidal pools", "marine biology", ["symbiosis", "scarcity"], ["pool", "anemone", "ebb"], "Tidal pools trap seawater at low tide and shelter small communities of animals.", ["beach", "water", "pool"]),
]
FIELDS = sorted({b[1] for b in BANK})


def _kw(b):
    return b[5] if len(b) > 5 else []


def pick(seed=None, prompt=None, k=3):
    """Choose k inspirations from DISTINCT fields. A prompt biases the pick: any bank name/word it mentions is included first."""
    if prompt:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) if seed is None else seed
    if seed is None:
        seed = random.SystemRandom().randrange(1, 10 ** 6)     # a truly random pick when no prompt/seed is given
    rnd = random.Random(seed)
    chosen = []
    if prompt:
        words = [w for w in re.findall(r"[a-z]+", prompt.lower()) if len(w) >= 4]
        def score(b, w):
            norm = b[0].lower().replace(" ", "").replace("'", "").replace("-", "")
            if w in norm:
                return 3                                           # the word is (part of) the idea's own name
            if w in [k for k in _kw(b)]:
                return 2                                           # exact keyword
            if any(m.startswith(w) or w.startswith(m) for m in list(b[3]) + _kw(b) if len(m) >= 4):
                return 1                                           # loose stem match
            return 0
        for w in dict.fromkeys(words):                      # one inspiration per prompt word: the best-scoring entries, distinct fields
            cand = [(score(b, w), b) for b in BANK if b not in chosen and all(b[1] != c[1] for c in chosen)]
            best = max((s for s, _ in cand), default=0)
            top = [b for s, b in cand if s == best and s > 0]
            if top and len(chosen) < k:
                chosen.append(rnd.choice(top))
    if prompt and len(chosen) >= 2:           # the user named the ideas to fuse: use exactly those, no random filler
        return chosen, seed
    pool = [b for b in BANK if b not in chosen]
    rnd.shuffle(pool)
    for b in pool:
        if len(chosen) >= k:
            break
        if all(b[1] != c[1] for c in chosen):
            chosen.append(b)
    return chosen, seed
