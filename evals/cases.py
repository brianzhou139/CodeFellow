"""Thirty deterministic repair cases for CodeFellow's local domain evaluation."""

from __future__ import annotations

from textwrap import dedent


def case(case_id: str, language: str, source: str, question: str, tests: str) -> dict:
    suffix = "py" if language == "python" else "js"
    return {
        "id": case_id,
        "language": language,
        "filename": f"{case_id}.{suffix}",
        "source": dedent(source).lstrip(),
        "question": question,
        "tests": dedent(tests).lstrip(),
    }


CASES = [
    case(
        "py01_longest_unique",
        "python",
        """
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
        """,
        "Fix the function. It must return 2 for 'abba' and preserve the sliding-window approach.",
        """
        assert longest_unique("") == 0
        assert longest_unique("abba") == 2
        assert longest_unique("abcabcbb") == 3
        assert longest_unique("bbbbb") == 1
        assert longest_unique("ééa") == 2
        """,
    ),
    case(
        "py02_average",
        "python",
        """
        def average(values):
            return sum(values) / len(values)
        """,
        "Return None for empty input, accept numbers or numeric strings, and raise ValueError for a nonnumeric value.",
        """
        assert average([]) is None
        assert average([1, 2, 3]) == 2
        assert average(["2", "4"]) == 3
        assert average([1, "2.5"]) == 1.75
        try:
            average(["x"])
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        """,
    ),
    case(
        "py03_binary_search",
        "python",
        """
        def binary_search(items, target):
            low = 0
            high = len(items) - 1
            while low <= high:
                mid = (low + high) // 2
                if items[mid] == target:
                    return mid
                if target < items[mid]:
                    high = mid
                else:
                    low = mid + 1
            return -1
        """,
        "Repair the boundary update so searches terminate and return -1 when the target is absent.",
        """
        assert binary_search([], 3) == -1
        assert binary_search([1], 1) == 0
        assert binary_search([1], 0) == -1
        assert binary_search([1, 3, 5, 7], 5) == 2
        assert binary_search([1, 3, 5, 7], 2) == -1
        """,
    ),
    case(
        "py04_dedupe_order",
        "python",
        """
        def dedupe(values):
            return list(set(values))
        """,
        "Remove duplicates while preserving the first-occurrence order. Inputs are hashable.",
        """
        assert dedupe([]) == []
        assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]
        assert dedupe(["b", "a", "b"]) == ["b", "a"]
        assert dedupe([0, False, 1]) == [0, 1]
        """,
    ),
    case(
        "py05_factorial",
        "python",
        """
        def factorial(number):
            if number == 1:
                return 1
            return number * factorial(number - 1)
        """,
        "Support zero correctly and raise ValueError for negative integers without changing the function name.",
        """
        assert factorial(0) == 1
        assert factorial(1) == 1
        assert factorial(5) == 120
        try:
            factorial(-1)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        """,
    ),
    case(
        "py06_clamp",
        "python",
        """
        def clamp(value, low, high):
            return min(low, max(high, value))
        """,
        "Clamp value into the inclusive low-to-high range. Assume low is not greater than high.",
        """
        assert clamp(-2, 0, 10) == 0
        assert clamp(4, 0, 10) == 4
        assert clamp(20, 0, 10) == 10
        assert clamp(3, 3, 3) == 3
        """,
    ),
    case(
        "py07_count_vowels",
        "python",
        """
        def count_vowels(text):
            return sum(1 for char in text if char in "aeiou")
        """,
        "Count English vowels case-insensitively while leaving non-ASCII characters harmless.",
        """
        assert count_vowels("") == 0
        assert count_vowels("AEIOU") == 5
        assert count_vowels("CodeFellow") == 4
        assert count_vowels("rhythm") == 0
        assert count_vowels("café") == 2
        """,
    ),
    case(
        "py08_merge_sorted",
        "python",
        """
        def merge_sorted(left, right):
            merged = []
            i = j = 0
            while i < len(left) and j < len(right):
                if left[i] <= right[j]:
                    merged.append(left[i])
                    i += 1
                else:
                    merged.append(right[j])
                    j += 1
            return merged
        """,
        "Complete the merge without sorting the combined inputs again.",
        """
        assert merge_sorted([], []) == []
        assert merge_sorted([1, 3], []) == [1, 3]
        assert merge_sorted([], [2, 4]) == [2, 4]
        assert merge_sorted([1, 4, 7], [2, 3, 8]) == [1, 2, 3, 4, 7, 8]
        assert merge_sorted([1, 1], [1]) == [1, 1, 1]
        """,
    ),
    case(
        "py09_is_prime",
        "python",
        """
        def is_prime(number):
            for divisor in range(2, int(number ** 0.5)):
                if number % divisor == 0:
                    return False
            return True
        """,
        "Correct the edge cases and square-root boundary for nonnegative integers.",
        """
        assert is_prime(0) is False
        assert is_prime(1) is False
        assert is_prime(2) is True
        assert is_prime(4) is False
        assert is_prime(9) is False
        assert is_prime(17) is True
        """,
    ),
    case(
        "py10_chunks",
        "python",
        """
        def chunks(items, size):
            return [items[index:index + size] for index in range(0, len(items) - size, size)]
        """,
        "Return consecutive chunks including a short final chunk, and raise ValueError when size is not positive.",
        """
        assert chunks([], 3) == []
        assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
        assert chunks([1, 2], 5) == [[1, 2]]
        try:
            chunks([1], 0)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        """,
    ),
    case(
        "py11_max_subarray",
        "python",
        """
        def max_subarray_sum(values):
            best = 0
            current = 0
            for value in values:
                current = max(0, current + value)
                best = max(best, current)
            return best
        """,
        "Return None for empty input and the largest nonempty contiguous sum otherwise, including all-negative arrays.",
        """
        assert max_subarray_sum([]) is None
        assert max_subarray_sum([-5]) == -5
        assert max_subarray_sum([-4, -2, -7]) == -2
        assert max_subarray_sum([4, -1, 2, 1]) == 6
        assert max_subarray_sum([1, -3, 5, -2, 4]) == 7
        """,
    ),
    case(
        "py12_rotate_right",
        "python",
        """
        def rotate_right(values, steps):
            steps %= len(values)
            return values[-steps:] + values[:-steps]
        """,
        "Return a rotated copy, handle empty input, and support steps larger than the list length.",
        """
        assert rotate_right([], 3) == []
        assert rotate_right([1, 2, 3], 0) == [1, 2, 3]
        assert rotate_right([1, 2, 3], 1) == [3, 1, 2]
        assert rotate_right([1, 2, 3], 4) == [3, 1, 2]
        """,
    ),
    case(
        "py13_parse_bool",
        "python",
        """
        def parse_bool(value):
            return bool(value)
        """,
        "Parse booleans and the case-insensitive strings true/false with surrounding whitespace; raise ValueError otherwise.",
        """
        assert parse_bool(True) is True
        assert parse_bool(False) is False
        assert parse_bool(" TRUE ") is True
        assert parse_bool("false") is False
        try:
            parse_bool("yes")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        """,
    ),
    case(
        "py14_second_largest",
        "python",
        """
        def second_largest(values):
            return sorted(values)[-2]
        """,
        "Return the second-largest distinct value, or None when fewer than two distinct values exist.",
        """
        assert second_largest([]) is None
        assert second_largest([5]) is None
        assert second_largest([5, 5]) is None
        assert second_largest([3, 1, 3, 2]) == 2
        assert second_largest([-1, -3, -2]) == -2
        """,
    ),
    case(
        "py15_balanced_brackets",
        "python",
        """
        def balanced(text):
            pairs = {")": "(", "]": "[", "}": "{"}
            stack = []
            for char in text:
                if char in "([{":
                    stack.append(char)
                elif char in pairs and stack:
                    stack.pop()
            return not stack
        """,
        "Validate matching bracket types and order while ignoring non-bracket characters.",
        """
        assert balanced("") is True
        assert balanced("a+(b*c)") is True
        assert balanced("([{}])") is True
        assert balanced("([)]") is False
        assert balanced("]") is False
        assert balanced("((") is False
        """,
    ),
    case(
        "js01_average",
        "javascript",
        """
        function average(values) {
          return values.reduce((sum, value) => sum + value) / values.length;
        }
        """,
        "Return null for an empty array, accept numbers or numeric strings, and throw TypeError for a nonnumeric value.",
        """
        const assert = require("node:assert/strict");
        assert.equal(average([]), null);
        assert.equal(average([1, 2, 3]), 2);
        assert.equal(average(["2", "4"]), 3);
        assert.equal(average([1, "2.5"]), 1.75);
        assert.throws(() => average(["x"]), TypeError);
        """,
    ),
    case(
        "js02_sum_positive",
        "javascript",
        """
        function sumPositive(values) {
          let total = 0;
          for (const value of values) {
            if (value) total += value;
          }
          return total;
        }
        """,
        "Sum only positive finite numbers. Ignore zero, negatives, numeric strings, NaN, and infinities.",
        """
        const assert = require("node:assert/strict");
        assert.equal(sumPositive([]), 0);
        assert.equal(sumPositive([1, -2, 3, 0]), 4);
        assert.equal(sumPositive(["5", 2]), 2);
        assert.equal(sumPositive([NaN, Infinity, 4]), 4);
        """,
    ),
    case(
        "js03_unique_order",
        "javascript",
        """
        function unique(values) {
          return [...new Set(values)].sort();
        }
        """,
        "Remove duplicates while preserving first-occurrence order.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(unique([]), []);
        assert.deepEqual(unique([3, 1, 3, 2, 1]), [3, 1, 2]);
        assert.deepEqual(unique(["b", "a", "b"]), ["b", "a"]);
        """,
    ),
    case(
        "js04_binary_search",
        "javascript",
        """
        function binarySearch(items, target) {
          let low = 0;
          let high = items.length;
          while (low < high) {
            const mid = Math.floor((low + high) / 2);
            if (items[mid] < target) low = mid + 1;
            else high = mid;
          }
          return low;
        }
        """,
        "Return the index of target in a sorted array, or -1 when absent.",
        """
        const assert = require("node:assert/strict");
        assert.equal(binarySearch([], 1), -1);
        assert.equal(binarySearch([1], 1), 0);
        assert.equal(binarySearch([1], 2), -1);
        assert.equal(binarySearch([1, 3, 5, 7], 5), 2);
        assert.equal(binarySearch([1, 3, 5, 7], 4), -1);
        """,
    ),
    case(
        "js05_palindrome",
        "javascript",
        """
        function isPalindrome(text) {
          return text === text.split("").reverse().join("");
        }
        """,
        "Check palindromes case-insensitively while ignoring non-alphanumeric ASCII characters.",
        """
        const assert = require("node:assert/strict");
        assert.equal(isPalindrome(""), true);
        assert.equal(isPalindrome("RaceCar"), true);
        assert.equal(isPalindrome("A man, a plan, a canal: Panama!"), true);
        assert.equal(isPalindrome("Code"), false);
        """,
    ),
    case(
        "js06_group_by",
        "javascript",
        """
        function groupBy(items, key) {
          const result = {};
          for (const item of items) {
            result[item[key]] = item;
          }
          return result;
        }
        """,
        "Group objects into arrays by the named property without losing earlier objects.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(groupBy([], "kind"), {});
        assert.deepEqual(groupBy([{kind:"a", n:1}, {kind:"b", n:2}, {kind:"a", n:3}], "kind"), {
          a: [{kind:"a", n:1}, {kind:"a", n:3}],
          b: [{kind:"b", n:2}]
        });
        """,
    ),
    case(
        "js07_range",
        "javascript",
        """
        function range(start, end, step = 1) {
          const values = [];
          for (let value = start; value <= end; value += step) values.push(value);
          return values;
        }
        """,
        "Return an end-exclusive increasing range and throw RangeError when step is not positive.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(range(0, 0), []);
        assert.deepEqual(range(0, 4), [0, 1, 2, 3]);
        assert.deepEqual(range(1, 6, 2), [1, 3, 5]);
        assert.deepEqual(range(5, 2), []);
        assert.throws(() => range(0, 2, 0), RangeError);
        """,
    ),
    case(
        "js08_find_max",
        "javascript",
        """
        function findMax(values) {
          let best = 0;
          for (const value of values) {
            if (value > best) best = value;
          }
          return best;
        }
        """,
        "Return null for empty input and the greatest number otherwise, including all-negative arrays.",
        """
        const assert = require("node:assert/strict");
        assert.equal(findMax([]), null);
        assert.equal(findMax([3]), 3);
        assert.equal(findMax([-5, -2, -8]), -2);
        assert.equal(findMax([1, 9, 4]), 9);
        """,
    ),
    case(
        "js09_count_words",
        "javascript",
        """
        function countWords(text) {
          return text.trim().split(/\\s+/).length;
        }
        """,
        "Count whitespace-separated words, returning zero for empty or whitespace-only text.",
        """
        const assert = require("node:assert/strict");
        assert.equal(countWords(""), 0);
        assert.equal(countWords("   \t\n"), 0);
        assert.equal(countWords("one"), 1);
        assert.equal(countWords(" one   two\nthree "), 3);
        """,
    ),
    case(
        "js10_parse_price",
        "javascript",
        """
        function parsePrice(text) {
          return Number(text.replace("$", ""));
        }
        """,
        "Parse prices containing optional dollar signs, commas, and surrounding whitespace; throw TypeError if the result is not finite.",
        """
        const assert = require("node:assert/strict");
        assert.equal(parsePrice("$12.50"), 12.5);
        assert.equal(parsePrice(" 1,234.00 "), 1234);
        assert.equal(parsePrice("$0"), 0);
        assert.throws(() => parsePrice("free"), TypeError);
        assert.throws(() => parsePrice("Infinity"), TypeError);
        """,
    ),
    case(
        "js11_chunk",
        "javascript",
        """
        function chunk(values, size) {
          const result = [];
          for (let index = 0; index < values.length; index += size) {
            result.push(values.slice(index, index + size - 1));
          }
          return result;
        }
        """,
        "Return consecutive chunks including a short final chunk, and throw RangeError when size is not positive.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(chunk([], 2), []);
        assert.deepEqual(chunk([1,2,3,4,5], 2), [[1,2],[3,4],[5]]);
        assert.deepEqual(chunk([1,2], 5), [[1,2]]);
        assert.throws(() => chunk([1], 0), RangeError);
        """,
    ),
    case(
        "js12_flatten_one",
        "javascript",
        """
        function flattenOne(values) {
          return values.flat(Infinity);
        }
        """,
        "Flatten exactly one array level and preserve deeper nested arrays.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(flattenOne([]), []);
        assert.deepEqual(flattenOne([1, [2, 3], 4]), [1, 2, 3, 4]);
        assert.deepEqual(flattenOne([[1, [2]], [[3]]]), [1, [2], [3]]);
        """,
    ),
    case(
        "js13_normalize_email",
        "javascript",
        """
        function normalizeEmail(value) {
          return value.toLowerCase();
        }
        """,
        "Trim and lowercase an email. Throw TypeError unless the trimmed value contains exactly one @ with text on both sides.",
        """
        const assert = require("node:assert/strict");
        assert.equal(normalizeEmail(" User@Example.COM "), "user@example.com");
        assert.equal(normalizeEmail("a@b"), "a@b");
        assert.throws(() => normalizeEmail("missing"), TypeError);
        assert.throws(() => normalizeEmail("a@@b"), TypeError);
        assert.throws(() => normalizeEmail("@b"), TypeError);
        """,
    ),
    case(
        "js14_frequency",
        "javascript",
        """
        function frequency(values) {
          const counts = {};
          for (const value of values) {
            counts[value] = (counts[value] || 1) + 1;
          }
          return counts;
        }
        """,
        "Return an object mapping each string value to its occurrence count.",
        """
        const assert = require("node:assert/strict");
        assert.deepEqual(frequency([]), {});
        assert.deepEqual(frequency(["a"]), {a: 1});
        assert.deepEqual(frequency(["a", "b", "a"]), {a: 2, b: 1});
        """,
    ),
    case(
        "js15_remove_nullish",
        "javascript",
        """
        function removeNullish(values) {
          return values.filter(Boolean);
        }
        """,
        "Remove only null and undefined. Preserve false, zero, empty strings, and NaN.",
        """
        const assert = require("node:assert/strict");
        const result = removeNullish([null, 0, false, "", undefined, NaN, 3]);
        assert.equal(result.length, 5);
        assert.equal(result[0], 0);
        assert.equal(result[1], false);
        assert.equal(result[2], "");
        assert.equal(Number.isNaN(result[3]), true);
        assert.equal(result[4], 3);
        """,
    ),
]


if len(CASES) != 30:
    raise RuntimeError(f"expected 30 cases, found {len(CASES)}")
