# Adapted from ed-donner/llm_engineering, week4/day3.ipynb (MIT, (c) 2024 Ed Donner).
# Changes: parameters come from the command line, and the program prints only its result.
# Timing is measured outside the program, so generated code can't misreport it.
"""Leibniz-style series for pi. Usage: python pi_series.py ITERATIONS PARAM1 PARAM2"""

import sys


def calculate(iterations, param1, param2):
    result = 1.0
    for i in range(1, iterations + 1):
        j = i * param1 - param2
        result -= 1 / j
        j = i * param1 + param2
        result += 1 / j
    return result


def main(argv):
    iterations, param1, param2 = (int(a) for a in argv[1:4])
    result = calculate(iterations, param1, param2) * 4
    print(f"Result: {result:.12f}")


if __name__ == "__main__":
    main(sys.argv)
