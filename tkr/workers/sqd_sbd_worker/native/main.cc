#include <iostream>
#include <fstream>
#include <chrono>
#include <random>
#include <deque>

#include <unistd.h>

#define _USE_MATH_DEFINES
#include <cmath>

#include "sbd/sbd.h"
#include "tierkreis.hpp"
#include "mpi.h"



int main(int argc, char * argv[]) {

  int provided;
  int mpi_ierr = MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);

  MPI_Comm comm = MPI_COMM_WORLD;
  int mpi_master = 0;
  int mpi_rank; MPI_Comm_rank(comm,&mpi_rank);
  int mpi_size; MPI_Comm_size(comm,&mpi_size);

  WorkerCall call;
  sbd::tpb::SBD sbd_data;

  std::string loadname("");
  std::string savename("");

  int L;
  int N;
  double energy;
  std::vector<double> density;
  std::vector<std::vector<size_t>> co_adet;
  std::vector<std::vector<size_t>> co_bdet;
  std::vector<std::vector<double>> one_p_rdm;
  std::vector<std::vector<double>> two_p_rdm;
  sbd::FCIDump fcidump;

  std::cout.precision(16);

  /**
     load worker inputs on rank 0
   */
  std::vector<std::vector<size_t>> adet;
  std::vector<std::vector<size_t>> bdet;
  if( mpi_rank == 0 ) {
    call = load_worker_call(argv[1]);
    load_worker_inputs(call,sbd_data,fcidump,adet);
    std::cout << "Loaded " << adet.size() << " alpha determinants." << std::endl;
  }

  int argument_count = static_cast<int>(call.arguments.size());
  MPI_Bcast(&argument_count,1,MPI_INT,0,comm);
  call.arguments.resize(argument_count);
  for(auto& argument : call.arguments) {
    int length = static_cast<int>(argument.size());
    MPI_Bcast(&length,1,MPI_INT,0,comm);
    argument.resize(length);
    MPI_Bcast(argument.data(),length,MPI_CHAR,0,comm);
  }
  if( mpi_rank != 0 ) {
    std::vector<char*> solver_argv;
    for(auto& argument : call.arguments) solver_argv.push_back(argument.data());
    solver_argv.push_back(nullptr);
    sbd_data = sbd::tpb::generate_sbd_data(argument_count,solver_argv.data());
  }
  sbd::MpiBcast(fcidump,0,comm);

  for(const auto & [key,value] : fcidump.header) {
    if( key == std::string("NORB") ) {
      L = std::atoi(value.c_str());
    }
    if( key == std::string("NELEC") ) {
      N = std::atoi(value.c_str());
    }
  }

  sbd::MpiBcast(adet,0,comm);
  bdet = adet;

  /**
     sample-based diagonalization using data for fcidump, adet, bdet.
   */
  sbd::tpb::diag(comm,sbd_data,fcidump,adet,bdet,loadname,savename,
              energy,density,co_adet,co_bdet,one_p_rdm,two_p_rdm);

  if( mpi_rank == 0 ) {
    std::cout << "Davidson energy: " << energy << std::endl;
    std::cout << "Number of carryover determinants: " << co_adet.size() << std::endl;
    write_worker_outputs(call,energy,density,co_adet,L,sbd_data.bit_length);
  }

  /**
     Finalize
  */

  MPI_Finalize();
  return 0;
}
