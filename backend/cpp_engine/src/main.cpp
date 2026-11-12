#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <sstream>
#include <iomanip>

struct Obstacle {
    double x;
    double y;
    double radius;
    std::string label;
};

struct ForbiddenZone {
    double x1, y1, x2, y2;
    std::string label;
};

struct SimResult {
    bool completed;
    int ticks;
    int violations;
    double total_energy_joules;
    double final_x;
    double final_y;
};

// Bit-exact kinematic simulation with pre-actuation safety supervisor
SimResult run_simulation(
    double start_x, double start_y,
    double target_x, double target_y,
    double dt, int max_ticks, double max_speed, double robot_radius,
    const std::vector<Obstacle>& obstacles,
    const std::vector<ForbiddenZone>& zones,
    bool apply_safety_shield,
    const std::string& fault_type
) {
    double x = start_x;
    double y = start_y;
    double vx = 0.0;
    double vy = 0.0;
    int violations = 0;
    double total_energy = 0.0;
    bool completed = false;
    int actual_ticks = 0;

    for (int tick = 0; tick < max_ticks; ++tick) {
        actual_ticks++;
        double dx = target_x - x;
        double dy = target_y - y;
        double dist = std::hypot(dx, dy);

        if (dist < 0.35) {
            completed = true;
            break;
        }

        // Nominal desired velocity towards target
        double des_vx = (dx / dist) * max_speed;
        double des_vy = (dy / dist) * max_speed;

        // Injected fault behavior
        if (fault_type == "actuator_stall" && tick >= 20 && tick <= 35) {
            des_vx = 0.0;
            des_vy = 0.0;
        } else if (fault_type == "perception_noise" && tick % 5 == 0) {
            des_vx += 0.25 * std::sin(static_cast<double>(tick));
            des_vy += 0.25 * std::cos(static_cast<double>(tick));
        }

        // Pre-actuation geometric safety gate (shield)
        if (apply_safety_shield) {
            double test_x = x + des_vx * dt;
            double test_y = y + des_vy * dt;
            bool unsafe = false;

            for (const auto& obs : obstacles) {
                if (std::hypot(test_x - obs.x, test_y - obs.y) < (obs.radius + robot_radius)) {
                    unsafe = true;
                    break;
                }
            }
            for (const auto& z : zones) {
                if (test_x >= (z.x1 - robot_radius) && test_x <= (z.x2 + robot_radius) &&
                    test_y >= (z.y1 - robot_radius) && test_y <= (z.y2 + robot_radius)) {
                    unsafe = true;
                    break;
                }
            }

            if (unsafe) {
                // Project velocity to orthogonal evasion
                double temp = des_vx;
                des_vx = -des_vy * 0.7;
                des_vy = temp * 0.7;
            }
        }

        // Apply dynamics and limits
        double cmd_speed = std::hypot(des_vx, des_vy);
        if (cmd_speed > max_speed) {
            des_vx = (des_vx / cmd_speed) * max_speed;
            des_vy = (des_vy / cmd_speed) * max_speed;
        }

        vx = des_vx;
        vy = des_vy;
        x += vx * dt;
        y += vy * dt;

        // Mechanical work proxy: kinetic + damping dissipation
        double power = 12.0 * (vx * vx + vy * vy) + 2.5 * std::hypot(vx, vy);
        total_energy += power * dt;

        // Constraint violation check
        for (const auto& obs : obstacles) {
            if (std::hypot(x - obs.x, y - obs.y) < (obs.radius + robot_radius)) {
                violations++;
            }
        }
        for (const auto& z : zones) {
            if (x >= (z.x1 - robot_radius) && x <= (z.x2 + robot_radius) &&
                y >= (z.y1 - robot_radius) && y <= (z.y2 + robot_radius)) {
                violations++;
            }
        }
    }

    return SimResult{completed, actual_ticks, violations, total_energy, x, y};
}

int main(int argc, char* argv[]) {
    bool shielded = false;
    std::string fault = "none";
    int seed = 42;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--shielded") shielded = true;
        else if (arg == "--fault" && i + 1 < argc) fault = argv[++i];
        else if (arg == "--seed" && i + 1 < argc) seed = std::stoi(argv[++i]);
    }

    std::vector<Obstacle> obstacles = {
        {3.0, 3.4, 0.85, "Rack A"},
        {6.5, 4.5, 1.10, "Rack B"},
        {9.7, 3.8, 0.80, "Rack C"}
    };

    std::vector<ForbiddenZone> zones = {
        {5.1, 0.8, 7.7, 2.2, "No-entry workcell"}
    };

    SimResult res = run_simulation(
        1.2, 1.3,
        11.4, 2.0,
        0.2, 300, 1.2, 0.22,
        obstacles, zones,
        shielded, fault
    );

    std::cout << "{\n";
    std::cout << "  \"engine\": \"VEAB C++ Deterministic Kinematic Simulator\",\n";
    std::cout << "  \"completed\": " << (res.completed ? "true" : "false") << ",\n";
    std::cout << "  \"ticks\": " << res.ticks << ",\n";
    std::cout << "  \"violations\": " << res.violations << ",\n";
    std::cout << "  \"energy_joules\": " << std::fixed << std::setprecision(2) << res.total_energy_joules << ",\n";
    std::cout << "  \"final_pos\": [" << res.final_x << ", " << res.final_y << "],\n";
    std::cout << "  \"shielded\": " << (shielded ? "true" : "false") << ",\n";
    std::cout << "  \"fault\": \"" << fault << "\",\n";
    std::cout << "  \"seed\": " << seed << "\n";
    std::cout << "}\n";

    return 0;
}

