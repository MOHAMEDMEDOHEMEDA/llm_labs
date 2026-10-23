// Hand-written reference port, used by the tests as a known-good answer.
#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv) {
    if (argc < 4) return 2;
    long long iterations = std::atoll(argv[1]);
    long long p1 = std::atoll(argv[2]);
    long long p2 = std::atoll(argv[3]);
    double result = 1.0;
    for (long long i = 1; i <= iterations; ++i) {
        result -= 1.0 / static_cast<double>(i * p1 - p2);
        result += 1.0 / static_cast<double>(i * p1 + p2);
    }
    std::printf("Result: %.12f\n", result * 4);
    return 0;
}
