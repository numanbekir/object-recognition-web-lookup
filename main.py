# Numan Bekir Özçelik - 04.09.2026
"""Ana uygulama"""

import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    return parser.parse_args()


def main():
    args = parse_args()
    print("Görüntülü Sohbet - kurulum iskeleti hazır. Debug:", args.debug)


if __name__ == "__main__":
    main()
