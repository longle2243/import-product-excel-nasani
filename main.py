from nasani.main import main


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng theo yêu cầu.")
        raise SystemExit(130)
