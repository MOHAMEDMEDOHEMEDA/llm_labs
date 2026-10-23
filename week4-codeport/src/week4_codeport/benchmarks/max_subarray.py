# Adapted from ed-donner/llm_engineering, week4/day5.ipynb (MIT, (c) 2024 Ed Donner).
# Changes: parameters come from the command line, and the program prints only its result.
# Timing is measured outside the program, so generated code can't misreport it.
"""Sum of maximum subarray sums over 20 LCG-generated arrays.

Usage: python max_subarray.py N INITIAL_SEED MIN_VAL MAX_VAL
"""

import sys


def lcg(seed, a=1664525, c=1013904223, m=2**32):
    value = seed
    while True:
        value = (a * value + c) % m
        yield value


def max_subarray_sum(n, seed, min_val, max_val):
    lcg_gen = lcg(seed)
    random_numbers = [next(lcg_gen) % (max_val - min_val + 1) + min_val for _ in range(n)]
    max_sum = float("-inf")
    for i in range(n):
        current_sum = 0
        for j in range(i, n):
            current_sum += random_numbers[j]
            if current_sum > max_sum:
                max_sum = current_sum
    return max_sum


def total_max_subarray_sum(n, initial_seed, min_val, max_val):
    total_sum = 0
    lcg_gen = lcg(initial_seed)
    for _ in range(20):
        seed = next(lcg_gen)
        total_sum += max_subarray_sum(n, seed, min_val, max_val)
    return total_sum


def main(argv):
    n, initial_seed, min_val, max_val = (int(a) for a in argv[1:5])
    result = total_max_subarray_sum(n, initial_seed, min_val, max_val)
    print("Total Maximum Subarray Sum (20 runs):", result)


if __name__ == "__main__":
    main(sys.argv)
