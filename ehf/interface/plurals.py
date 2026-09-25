def polish_count(total: int, one: str, few: str, many: str) -> str:
    count = int(total)
    ending = count % 10
    hundred = count % 100
    if count == 1:
        word = one
    elif 2 <= ending <= 4 and not 12 <= hundred <= 14:
        word = few
    else:
        word = many
    return f"{count} {word}"
