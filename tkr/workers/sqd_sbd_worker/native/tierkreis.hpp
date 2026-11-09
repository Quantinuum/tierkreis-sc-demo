#pragma once

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace fs = std::filesystem;
using Json = nlohmann::json;

struct WorkerCall {
  std::string function_name;
  std::map<std::string, fs::path> inputs;
  std::map<std::string, fs::path> outputs;
  std::vector<std::string> arguments{"diag"};
};

inline Json read_json(const fs::path& path) {
  std::ifstream input;
  input.exceptions(std::ios::failbit | std::ios::badbit);
  input.open(path);
  return Json::parse(input);
}

// Call I/O helpers on rank 0; broadcast the loaded solver data before diag.
inline WorkerCall load_worker_call(const fs::path& path) {
  auto json = read_json(path);
  WorkerCall call;
  call.function_name = json.at("function_name").get<std::string>();
  for (const auto& [name, path] : json.at("inputs").items()) {
    call.inputs.emplace(name, path.get<std::string>());
  }
  for (const auto& [name, path] : json.at("outputs").items()) {
    call.outputs.emplace(name, path.get<std::string>());
  }
  auto arguments = read_json(call.inputs.at("solver_args"));
  for (const auto& argument : arguments) {
    call.arguments.push_back(argument.get<std::string>());
  }
  return call;
}

inline void load_worker_inputs(
    WorkerCall& call, sbd::tpb::SBD& settings, sbd::FCIDump& fcidump,
    std::vector<std::vector<size_t>>& adet) {
  std::vector<char*> argv;
  for (auto& argument : call.arguments) argv.push_back(argument.data());
  argv.push_back(nullptr);
  settings = sbd::tpb::generate_sbd_data(
      static_cast<int>(call.arguments.size()), argv.data());
  fcidump = sbd::LoadFCIDump(call.inputs.at("fcidump").string());
  const int norb = std::stoi(fcidump.header.at("NORB"));
  // Asset names need no extension; LoadAlphaDets dispatches by suffix.
  adet = sbd::DecodeAlphaDets(call.inputs.at("alpha_dets").string(), norb);
  sbd::change_bitlength(1, adet, settings.bit_length);
  sbd::sort_bitarray(adet);
}

inline std::ofstream output_file(const fs::path& path) {
  std::ofstream output;
  output.exceptions(std::ios::failbit | std::ios::badbit);
  output.open(path, std::ios::binary);
  output.precision(std::numeric_limits<double>::max_digits10);
  return output;
}

inline void write_worker_outputs(
    const WorkerCall& call, double energy, const std::vector<double>& density,
    const std::vector<std::vector<size_t>>& carryover, int norb,
    size_t bit_length) {
  for (const auto& [name, path] : call.outputs) {
    auto output = output_file(path);
    if (name == "energy") {
      output << Json(energy);
    } else if (name == "occ_a" || name == "occ_b") {
      for (size_t i = name == "occ_a" ? 0 : 1; i < density.size(); i += 2) {
        output << density[i] << '\n';
      }
    } else if (name == "carryover") {
      const size_t bytes_per_config = (norb + 7) / 8;
      std::vector<uint8_t> bytes(bytes_per_config);
      for (const auto& det : carryover) {
        std::fill(bytes.begin(), bytes.end(), 0);
        for (int j = 0; j < norb; ++j) {
          const size_t rev = norb - 1 - j;
          const bool bit = (det[rev / bit_length] >> (rev % bit_length)) & 1ULL;
          bytes[j / 8] |= static_cast<uint8_t>(bit << (7 - j % 8));
        }
        output.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
      }
    } else {
      throw std::runtime_error("Unknown SBD output: " + name);
    }
    output.close();
  }
}
