def longest_unique(text):
    seen = set()
    left = 0
    best = 0
    for right, char in enumerate(text):
        if char in seen:
            seen.remove(text[left])
            left += 1
        seen.add(char)
        best = max(best, right - left + 1)
    return best


print(longest_unique("abba"))
