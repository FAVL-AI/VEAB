CXX ?= /usr/bin/clang++
CXXFLAGS ?= -std=c++20 -O3 -Wall -Wextra

all: ../bin/veab-cpp-sim

../bin/veab-cpp-sim: src/main.cpp
	mkdir -p ../bin
	$(CXX) $(CXXFLAGS) src/main.cpp -o ../bin/veab-cpp-sim

clean:
	rm -f ../bin/veab-cpp-sim

