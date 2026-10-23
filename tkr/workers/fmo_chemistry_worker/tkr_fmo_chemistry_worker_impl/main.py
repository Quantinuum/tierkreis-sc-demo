from sys import argv

from tkr_fmo_chemistry_worker_impl import worker


def main() -> None:
    worker.app(argv)


if __name__ == "__main__":
    main()
