"""Accuracy check for account_classify, against REAL bios with hand-assigned labels.

Ground truth = the categories a human assigned on 2026-08-16 after reading each of these
bios individually. The bios are verbatim from the live profiles fetched that round, so
this is a real regression suite, not invented fixtures.

Run: python test_account_classify.py
"""

from account_classify import classify_from_profile, BRAND

# (handle, name, bio, expected) — expected is the 2026-08-16 human label.
CASES = [
    # --- organisational: leagues / federations / teams
    ("weareteamindia", "Indian Olympic Association", "Official handle of the Indian Olympic Association", "league"),
    ("cabcricket", "Cricket Association Of Bengal", "The official handle", "league"),
    ("gcamotera", "Gujarat Cricket Association", "Gujarat Cricket Association", "league"),
    ("indiansuperleague", "Indian Super League", "The official Instagram handle of the Indian Super League.", "league"),
    ("delhipremierleaguet20", "Delhi Premier League T20", "The pinnacle of T20 cricket in Delhi.", "league"),
    ("e1series", "E1 Series", "UIM E1 World Championship presented by PIF", "league"),
    ("ohiostatefb", "Ohio State Football", "Official IG for The Ohio State Football", "team"),
    ("ohiostathletics", "Ohio State Athletics", "The OFFICIAL content feed for The Ohio State Department of Athletics.", "team"),

    # --- institutional coaching -> other (kept for breadth, not a standalone creator)
    ("saniamirzatennisacademy", "Sania Mirza Tennis Academy", "@mirzasaniar's home ground. Registerations open now for HPT Camp", "other"),
    ("inspireinstituteofsport", "Inspire Institute of Sport", "Inspire Institute of Sport", "other"),
    ("neerajchoprafoundation", "Neeraj Chopra Foundation", "The official foundation", "other"),
    ("fitnessstandardscouncil", "Fitness Standards & Safety Council", "Fitness Standards and Safety Council", "other"),

    # --- brands: must NOT get a creator category at all
    ("sporting.beyond", "Sporting Beyond Pvt Ltd", "Innovate | Engage", BRAND),

    # --- athletes
    ("ajinkyarahane", "Ajinkya Rahane", "Indian Cricketer  Fitness enthusiast For business queries", "athlete"),
    ("leanderpaes", "Leander Paes", "Pro Tennis Player Former World No.1 World Record 7 Olympics 20 Grand Slam Titles", "athlete"),
    ("gkgurpreet", "GSS", "Keeper @indianfootball @bengalurufc", "athlete"),
    ("willjacks9", "Will Jacks", "Cricketer @englandcricket @surrey", "athlete"),
    ("nadinedeklerk32", "Nadine De Klerk", "Professional cricketer  Enquiries to jalder@tgisport.com", "athlete"),
    ("ashiquekuruniyan22", "Ashique Kuruniyan", "Professional footballer @indianfootball @bengalurufc", "athlete"),
    ("sivasakthi_ss11", "SivaSakthi", "Professional Football player @bengalurufc - Bengaluru", "athlete"),
    # The ordering case: a human athlete who also PRESIDES over a federation.
    ("ptushaofficial", "P.T.Usha", "Olympian - Track & Field Athlete | Member of Parliament - Rajya Sabha | President - Indian Olympic Association", "athlete"),

    # --- fitness (individual coaches/trainers posting their own content)
    ("ishaanphysio", "Dr Ishaan Marwaha(PT)", "Elite Performance & Recovery Specialist Helping Athletes Move Better Recover faster", "fitness_influencer"),
    ("waynelombardsa", "Wayne Lombard", "PhD (Med ExSci) | Exercise Sci | Biokinetics | S&C | Director @apatrainingsystems", "fitness_influencer"),
    ("dietmmonetization", "Coach Rajan", "DM CHANGE TO TRANSFORM get better with Cravings| PCOS |Diabetes", "fitness_influencer"),
    ("suhan.khnofficial", "Suhan Khan- Coach & PT Mentor", "Coach and PT Mentor", "fitness_influencer"),
    ("eliteedgefitness09", "Elite Edge", "Online Trainings  Personalised Training  Nutrition  Lifestyle Change", "fitness_influencer"),

    # --- lifestyle
    ("jimmysheirgill", "Jimmy Shergill", "Actor", "lifestyle_influencer"),
    ("juhi.bhatt", "Juhi Bhatt", "Actor", "lifestyle_influencer"),
    ("nikkhiladvani", "Nikkhil Advani", "Film maker.", "lifestyle_influencer"),
    ("singer_shaan", "Shaan Mukherji", "Label: @shaanmusiclabel", "lifestyle_influencer"),
    ("careerjourneyy", "Abhi Sharma", "Podcast Host  Stories That Inspire  1M+ views", "lifestyle_influencer"),
    ("taarukraina", "Taaruk Raina", "Happy thoughts, sad songs  Music/ Live", "lifestyle_influencer"),
    ("mohitvaru", "Mohitt Vaaru", "Advertising & Fashion Photographer Visual storytelling for brands & people", "lifestyle_influencer"),
    ("technicalguruji", "Gaurav Chaudhary", "Engineer by Education, YouTuber by Profession", "lifestyle_influencer"),

    # --- genuinely unclassifiable: empty/uninformative bios. 'other' is the HONEST
    # answer here, not a default -- the evidence string must say so.
    ("ranjeet_tiwari", "Ranjeet Tiwari", "", "other"),
    ("mamta_dp", "Mamta Rawat", "", "other"),
    ("sandrenzi", "Sandro S.", "@bengalurufc", "other"),
]


def main() -> int:
    hits = misses = 0
    failures = []
    for handle, name, bio, expected in CASES:
        got, why = classify_from_profile(name, bio, handle)
        if got == expected:
            hits += 1
        else:
            misses += 1
            failures.append((handle, expected, got, why))

    total = hits + misses
    print(f"agreement with human labels: {hits}/{total} ({100*hits/total:.0f}%)")
    if failures:
        print("\nDISAGREEMENTS (expected -> got):")
        for handle, exp, got, why in failures:
            print(f"  @{handle:<26} {exp} -> {got}")
            print(f"      {why}")
    return 0 if misses == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
