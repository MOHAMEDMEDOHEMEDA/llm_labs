// Hand-written reference port, used by the tests as a known-good answer.
// Kadane's algorithm gives the same maximum as the Python O(n^2) loop.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

static uint64_t next_lcg(uint64_t value) {
    return (1664525ULL * value + 1013904223ULL) % 4294967296ULL;
}

static long long max_subarray_sum(long long n, uint64_t seed, long long lo, long long hi) {
    const uint64_t range = static_cast<uint64_t>(hi - lo + 1);
    uint64_t value = seed;
    long long best = 0, current = 0;
    bool first = true;
    for (long long k = 0; k < n; ++k) {
        value = next_lcg(value);
        long long x = static_cast<long long>(value % range) + lo;
        current = first ? x : std::max(x, current + x);
        best = first ? x : std::max(best, current);
        first = false;
    }
    return best;
}

int main(int argc, char** argv) {
    if (argc < 5) return 2;
    long long n = std::atoll(argv[1]);
    uint64_t seed = std::strtoull(argv[2], nullptr, 10);
    long long lo = std::atoll(argv[3]), hi = std::atoll(argv[4]);
    long long total = 0;
    uint64_t gen = seed;
    for (int r = 0; r < 20; ++r) {
        gen = next_lcg(gen);
        total += max_subarray_sum(n, gen, lo, hi);
    }
    std::printf("Total Maximum Subarray Sum (20 runs): %lld\n", total);
    return 0;
}
