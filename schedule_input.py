import numpy as np


def expand_schedule(pattern, days):
    schedule = []
    while len(schedule) < days:
        schedule.extend(pattern)
    return schedule[:days]


def generate_optimized_schedule(days=30):
    """
    Simulated optimizer output (multi-drug therapy)
    """

    weekly_A = [1,0,0,1,1,0,0]
    weekly_B = [0,1,0,0,1,0,1]
    weekly_C = [0,0,1,0,0,1,0]

    schedule = {
        "Drug_A": np.array(expand_schedule(weekly_A, days)),
        "Drug_B": np.array(expand_schedule(weekly_B, days)),
        "Drug_C": np.array(expand_schedule(weekly_C, days))
    }

    return schedule


def generate_standard_schedule(days=30):
    """
    Simulated standard chemotherapy schedule
    """

    weekly_A = [1,0,1,0,1,0,1]
    weekly_B = [0,1,0,1,0,1,0]
    weekly_C = [0,0,0,0,0,0,0]

    schedule = {
        "Drug_A": np.array(expand_schedule(weekly_A, days)),
        "Drug_B": np.array(expand_schedule(weekly_B, days)),
        "Drug_C": np.array(expand_schedule(weekly_C, days))
    }

    return schedule


def generate_generic_schedule(drugs=None, days=30, optimized=True):
    drugs = list(drugs) if drugs else ["Drug_A", "Drug_B", "Drug_C"]
    schedule = {}

    for index, drug in enumerate(drugs):
        if optimized:
            pattern = [1 if (day + index) % 3 != 2 else 0 for day in range(7)]
        else:
            cycle_length = max(len(drugs), 2)
            pattern = [1 if (day + index) % cycle_length == 0 else 0 for day in range(7)]

        schedule[drug] = np.array(expand_schedule(pattern, days))

    return schedule


def generate_standard_schedule_for_drugs(drugs=None, days=30):
    return generate_generic_schedule(drugs=drugs, days=days, optimized=False)


def print_schedule(schedule):

    print("\nDrug Schedule\n")

    for drug in schedule:

        print(f"\n{drug}")

        for day,val in enumerate(schedule[drug]):

            status = "Given" if val == 1 else "None"

            print(f"Day {day+1}: {status}")