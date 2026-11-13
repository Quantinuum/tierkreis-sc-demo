from sys import argv

from tkr_sqd_quantum_worker_impl import worker


def main():
    worker.app(argv)


if __name__ == "__main__":
    main()
