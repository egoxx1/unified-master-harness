from stay.dates import days_between, parse

RATE_CENTS = 8900  # per night


def nights(check_in, check_out):
    return days_between(parse(check_in), parse(check_out)) - 1


def price(check_in, check_out):
    return nights(check_in, check_out) * RATE_CENTS
