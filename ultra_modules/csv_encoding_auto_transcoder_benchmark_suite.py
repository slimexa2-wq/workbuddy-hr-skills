import time
import random
import datetime

def transcode_csv_to_utf8(input_bytes: bytes, fallback_encoding: str = 'utf-8') -> str:
    """
    Attempts to decode a byte string using a list of common encodings.
    Prioritizes utf-8-sig to handle BOM, then utf-8, gb18030, etc.
    Falls back to `fallback_encoding` with `errors='replace'` to handle dirty data self-healing.
    """
    if not isinstance(input_bytes, bytes):
        if input_bytes is None:
            input_bytes = b''
        else:
            try:
                input_bytes = bytes(input_bytes)
            except TypeError:
                input_bytes = str(input_bytes).encode('utf-8')

    encodings_to_try = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'gb2312']

    for encoding in encodings_to_try:
        try:
            return input_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    # If all fail, fallback with replace for self-healing
    return input_bytes.decode(fallback_encoding, errors='replace')


def generate_synthetic_fixture(size: int = 10000, encoding: str = 'utf-8') -> bytes:
    """
    Generates a synthetic CSV byte string with cross-year/month boundaries,
    missing values, and extreme edge cases.
    """
    header = "ID,Name,Date,Attendance,Salary,Remarks\n"
    rows = []

    start_date = datetime.date(2023, 12, 28)

    for i in range(size):
        # Cross-year and cross-month dates
        current_date = start_date + datetime.timedelta(days=i % 10)
        date_str = current_date.strftime("%Y-%m-%d")

        # Missing values and random data
        name = f"Employee_{i}" if i % 10 != 0 else "" # 10% missing names
        attendance = "Present" if i % 5 != 0 else "Absent"
        salary = f"{random.randint(3000, 15000)}" if i % 20 != 0 else "" # 5% missing salaries
        remarks = "Normal"
        if i % 100 == 0:
            remarks = "特殊边界测试：跨年，跨月" # Special chars to test encoding

        row = f"{i},{name},{date_str},{attendance},{salary},{remarks}\n"
        rows.append(row)

    csv_string = header + "".join(rows)
    return csv_string.encode(encoding, errors='replace')


def run_benchmark():
    """
    Tests transcoding performance on synthetic fixtures.
    """
    print("Running benchmarks...")
    sizes = [1000, 10000, 100000]
    encodings = ['utf-8', 'gb18030', 'utf-8-sig']

    for size in sizes:
        for enc in encodings:
            fixture = generate_synthetic_fixture(size=size, encoding=enc)

            start_time = time.perf_counter()
            _ = transcode_csv_to_utf8(fixture)
            end_time = time.perf_counter()

            duration_ms = (end_time - start_time) * 1000
            print(f"Size: {size}, Encoding: {enc}, Time: {duration_ms:.2f} ms")

if __name__ == '__main__':
    run_benchmark()
