// A plausible wrong port: 32-bit arithmetic overflows in the LCG.
#include <algorithm>
#include <cstdio>
#include <cstdlib>

static unsigned int next_lcg(unsigned int v) { return 1664525u * v + 1013904223u; }

int main(int argc, char** argv) {
    int n = std::atoi(argv[1]);
    unsigned int gen = static_cast<unsigned int>(std::atoll(argv[2]));
    int lo = std::atoi(argv[3]), hi = std::atoi(argv[4]);
    long long total = 0;
    for (int r = 0; r < 20; ++r) {
        gen = next_lcg(gen);
        unsigned int v = gen;
        int best = 0, cur = 0;
        for (int k = 0; k < n; ++k) {
            v = next_lcg(v);
            int x = static_cast<int>(v % static_cast<unsigned int>(hi - lo + 1)) + lo;
            cur = k == 0 ? x : std::max(x, cur + x);
            best = k == 0 ? x : std::max(best, cur);
        }
        total += best;
    }
    std::printf("Total Maximum Subarray Sum (20 runs): %lld\n", total);
}
