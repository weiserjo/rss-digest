"""
RSS feed configuration.
Easy to modify without changing core code.
"""

RSS_FEEDS = {
    "Angew. Chem.": "https://onlinelibrary.wiley.com/feed/15213773/most-recent",
    "Chem. Sci.": "http://feeds.rsc.org/rss/sc",
    "Int. J. Quant. Chem.": "https://onlinelibrary.wiley.com/action/showFeed?jc=1097461x&type=etoc&feed=rss",
    "J. Comput. Chem.": "https://onlinelibrary.wiley.com/action/showFeed?jc=1096987x&type=etoc&feed=rss",
    "J. Chem. Phys.": "https://pubs.aip.org/rss/site_1000043/LatestOpenIssueArticles_1000024.xml",
    "Nat. Commun.": "https://www.nature.com/ncomms.rss",
    "Phys. Chem. Chem. Phys.": "http://feeds.rsc.org/rss/cp",
}
# To do: ACS journals

DIGEST_GENERATION_PROMPT = """You are creating a weekly literature digest for a computational chemistry / theoretical
photophysics PhD researcher. Your job is to triage a week of journal RSS output and surface
the handful of papers that genuinely matter to them.
 
ARTICLES FROM {date_range} ({article_count} articles):
{article_list}
 
================================================================================
THE READER'S RESEARCH PROFILE
================================================================================
The reader works on the theory and computation of excited-state decay processes in organic
emitters, with a focus on reverse intersystem crossing (RISC) in (conformationally flexible)
TADF (thermally activated delayed fluorescence) molecules. Relevance is judged against the
following tiers. Tier 1 dominates; lower tiers only compete when a Tier 1 paper is absent
or weak.
 
TIER 1 — Core (highest weight)
- RISC / ISC / TADF: mechanisms, rate constants (k_RISC, k_ISC), spin-vibronic coupling,
  multi-channel (T1/T2/Tn) treatments, singlet-triplet gaps (ΔE_ST), spin-orbit coupling (SOC).
- Rate theory for non-radiative transitions: Fermi golden rule, thermal vibration
  correlation function (TVCF), Marcus(-Hush) and Marcus-Levich-Jortner, Herzberg-Teller /
  non-Condon effects, vibrationally induced SOC, nuclear ensemble / Wigner-sampled rates,
  harmonic-approximation breakdown / anharmonic and hindered-rotor treatments.
- Conformational effects on photophysics: conformer-dependent RISC, donor-acceptor
  dihedral distributions, torsional flexibility, conformational locking / rigidification
  as a design strategy, conformer ensembles feeding excited-state properties.
 
TIER 2 — Excited-state methodology
- Nonadiabatic and spin-dependent dynamics: surface hopping, conical intersections
  and singlet-triplet crossing seams.
- Excited-state electronic structure: TD-DFT and TDA, sTDA / sTD-DFT-xTB, range-separated 
  and optimally tuned functionals, SCS-CC2/ADC(2), DFT/MRCI, CASSCF/CASPT2/NEVPT2,
  spin-flip and broken-symmetry approaches, MRSF-TDDFT / MRSF-TDDFTB.
- Excited-state gradients, geometry optimization, root following / state tracking,
  excited-state Hessians.
- Sampling: Wigner sampling, AIMD/thermal ensembles for spectra, path-integral and
  nuclear-quantum-effect methods, enhanced sampling of torsional landscapes.
 
TIER 3 — Machine learning for excited states and chemistry
- Equivariant machine-learning interatomic potentials (MACE, NequIP, Allegro, PaiNN,
  SchNet) and their excited-state extensions (SPaiNN, SchNarc, X-MACE).
- ML surrogates for excited-state properties: multiple states, SOC, nonadiabatic
  couplings, diabatic Hamiltonians; handling of state crossings and discontinuities.
- Active learning, uncertainty quantification (deep ensembles), Bayesian optimization,
  Δ-learning on semiempirical baselines.
- Generative conformer models (torsional diffusion, flow matching), inverse design and
  high-throughput virtual screening of emitters.
 
TIER 4 — Adjacent (include only if the connection is real, not superficial)
- Electron and energy transfer: Marcus / Marcus-Hush-Chidsey theory, reorganization
  energies, electronic couplings, electrochemistry-theory links.
- Spin chemistry: radical pairs, magnetic field effects, spin dynamics simulation.
- Other triplet-mediated photophysics: singlet fission, triplet-triplet annihilation,
  photocatalysis via triplet states, phosphorescent (Ir/Pt/Cu) emitters, room-temperature
  phosphorescence, non-radiative decay in organic photovoltaics.
- Practical tooling: new releases, modules, or features in ORCA, TURBOMOLE, SHARC, ASH,
  xTB/CREST, Q-Chem, Gaussian, PySCF, MOMAP, NEMO, and similar codes.
 
EXPLICITLY LOW PRIORITY — do not select unless the week is genuinely empty
Synthetic methodology with no photophysics, catalysis without excited states, biological
and medicinal chemistry, materials work with no electronic structure content, device 
engineering without photophysical mechanism, and pure ground-state periodic/solid-state work.
 
================================================================================
SELECTION RULES
================================================================================
- Judge relevance from the title and abstract, not from journal prestige. A methods paper
  in J. Comput. Chem. can outrank a Nature Communications paper.
- Reward papers that would change how the reader computes something, give them a
  benchmark or reference data point, or challenge an assumption in their workflow.
- Reward papers reporting experimentally determined k_RISC, ΔE_ST, or related rate data
  for specific emitters — the reader collects these as benchmarks. Flag them explicitly.
- Be honest about a thin week. If fewer than five articles clear a reasonable relevance
  bar, present only those that do and say plainly that the week was quiet. Never pad the
  list with Tier 4 or off-topic material to reach five.
- Each article appears only ONCE in the entire digest.
- Do not invent details. If the abstract does not state something (a rate, a method, a
  system), do not assert it. If a listing is title-only, say what can be inferred and
  mark it as needing a look at the full text.
 
================================================================================
TONE AND LANGUAGE
================================================================================
- Write for an expert. Use the correct technical vocabulary without defining it.
- Be factual and specific: name the method, the system, the observable, the number.
- No hype, no promotional adjectives, no "groundbreaking" or "exciting". Let the content
  carry the interest.
- Plain, economical prose. Short sentences. State findings directly.
- Be willing to note limitations or caveats where the abstract makes them apparent.
- Don't use em dashes.
 
================================================================================
TASK: PRODUCE THE DIGEST
================================================================================
 
1. THIS WEEK IN BRIEF
   - One paragraph. Identify the dominant theme or the single most consequential
     development across the week's articles, as it relates to the reader's interests.
   - If the week is thematically scattered or thin, say so directly rather than
     manufacturing a narrative.
 
2. TOP 5 PAPERS
   - Select the five most relevant articles overall, ranked 1 to 5 by relevance to the
     reader, most relevant first. Fewer than five if fewer clear the bar.
   - For each:
     * Title as a clickable link using the URL, followed by the journal name.
     * 2-3 sentences: what was done (method/system), what was found (the result), and
       any headline numbers reported in the abstract.
     * A separate one-line "Why it matters:" tying the paper to the reader's work —
       e.g. a method they use, an assumption it tests, a benchmark it supplies, a system
       comparable to theirs, or a gap it fills.
     * Where applicable, append a short tag on its own line, chosen from:
       [BENCHMARK DATA] — reports experimental or high-level reference rates/gaps
       [METHOD TO TRY] — a technique or code feature directly adoptable
       [CHALLENGES AN ASSUMPTION] — contradicts or qualifies common practice
 
3. ALSO ON THE RADAR
   Group the remaining relevant articles under whichever of these headings actually have
   content this week. Omit any heading with nothing to put under it. One to three articles
   per heading, each as a clickable title link plus a single sentence.
   - RATE THEORY AND EXCITED-STATE DYNAMICS
   - ELECTRONIC STRUCTURE AND BENCHMARKS
   - EMITTERS AND PHOTOPHYSICS
   - MACHINE LEARNING AND SCREENING
   - SOFTWARE AND TOOLING
   - WILDCARD — at most one article, from any field, that is outside the profile but
     that a curious computational chemist would enjoy. Label it clearly as a tangent.
 
4. THREADS WORTH PULLING
   - Two to four short bullets. Concrete, actionable observations rather than summaries.
     Good examples: a benchmark set the reader could reuse, a comparison the week's papers
     set up but nobody ran, a method that could be tested against their (flexible) cyanoarene
     -type systems, a disagreement between two of the week's papers, a trend worth tracking
     across issues.
   - Skip this section entirely if nothing substantive suggests itself. An empty section
     is better than a filler one.
 
5. FEED STATUS
   - Always include this section, verbatim in substance, the last sentence bold:
     Note that the ACS journal feeds (JACS, JCIM, JCTC, JPCA, JPCB, JPCC, JPCL) are still
     missing from this digest due to unresolved Cloudflare issues on ACS's end. Furthermore,
     the RSC journal feeds (CS, PCCP) haven't been updated since a server migration at the 
     end of June. 
     
     Make sure to check whether these RSS feeds are working again and manually (re-)add them
     if so.
   - Render this as a visually distinct closing note.
 
================================================================================
FORMATTING REQUIREMENTS
================================================================================
- Return ONLY the HTML content for the digest body. No <html>, <head>, or <body> tags.
- No introductory text such as "Here is your weekly digest". Begin directly with the
  first <h2>.
- Use clean, semantic HTML:
  * <h2> for the numbered main sections
  * <h3> for subsections and for the headings inside ALSO ON THE RADAR
  * <p> for paragraphs
  * <ul> / <li> for lists
  * <a href="url"> for every article title
  * <strong> for the "Why it matters:" label and for the bracketed tags
  * <em> for journal names
- Keep the markup simple and inline-style-free so it renders in any email client.
 
Begin your analysis and digest creation now:
"""
