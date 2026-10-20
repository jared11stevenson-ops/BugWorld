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
]
FIELDS = sorted({b[1] for b in BANK})


def pick(seed=None, prompt=None, k=3):
    """Choose k inspirations from DISTINCT fields. A prompt biases the pick: any bank name/word it mentions is included first."""
    if prompt:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) if seed is None else seed
    if seed is None:
        seed = random.SystemRandom().randrange(1, 10 ** 6)     # a truly random pick when no prompt/seed is given
    rnd = random.Random(seed)
    chosen = []
    if prompt:
        words = set(re.findall(r"[a-z]+", prompt.lower()))
        for b in BANK:
            if len(chosen) < k and (b[0].lower() in prompt.lower() or any(len(m) >= 4 and (w.startswith(m) or m.startswith(w)) for w in words if len(w) >= 4 for m in b[3])) and all(b[1] != c[1] for c in chosen):
                chosen.append(b)
    pool = [b for b in BANK if b not in chosen]
    rnd.shuffle(pool)
    for b in pool:
        if len(chosen) >= k:
            break
        if all(b[1] != c[1] for c in chosen):
            chosen.append(b)
    return chosen, seed
