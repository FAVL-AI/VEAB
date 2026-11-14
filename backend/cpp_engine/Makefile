CXX ?= /usr/bin/clang++
CXXFLAGS ?= -std=c++20 -O3 -Wall -Wextra

all: ../bin/veap-cpp-sim

../bin/veap-cpp-sim: src/main.cpp
	mkdir -p ../bin
	$(CXX) $(CXXFLAGS) src/main.cpp -o ../bin/veap-cpp-sim

clean:
	rm -f ../bin/veap-cpp-sim

