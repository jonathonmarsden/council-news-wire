from core.utils import parse_date
import datetime

def test_date_hallucinations():
    scenarios = [
        ("Posted on 12 January 2026", "Valid Date"),
        ("Lot 112 DP 755126", "Narromine Bad Data"),
        ("3270 Chapman Valley Road", "Chapman Valley Bad Data"),
        ("Vision 2030 Strategy", "Future Year text"),
        ("Contact us on 0400 123 456", "Phone number"),
        ("Reference: 25/1234", "File number that looks like date"),
        ("40 Years of Service", "Waverley Duration")
    ]
    
    print(f"{'Input String':<40} | {'Parsed Date':<20} | {'Verdict'}")
    print("-" * 80)
    
    for text, label in scenarios:
        dt = parse_date(text)
        dt_str = dt.strftime("%Y-%m-%d") if dt else "None"
        print(f"{text:<40} | {dt_str:<20} | {label}")

if __name__ == "__main__":
    test_date_hallucinations()