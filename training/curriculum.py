"""Held-out-safe repair seeds for CodeFellow adaptation.

These examples are intentionally different from the public and frozen evaluation
tasks. Every full solution is executed by build_dataset.py before it is emitted.
"""

CURRICULUM = [
    {
        "id": "py_median_value",
        "runtime": "python",
        "buggy": """def median_value(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle]
""",
        "prompt_en": "Return None for an empty list and the statistical median for odd or even input lengths without changing the input.",
        "prompt_af": "Gee None vir 'n leë lys terug en die statistiese mediaan vir onewe of ewe invoerlengtes sonder om die invoer te verander.",
        "diagnostic_en": "The implementation returns only the upper middle value for even-sized lists and crashes on empty input.",
        "diagnostic_af": "Die implementering gee net die boonste middelwaarde vir ewe-groot lyste terug en faal met leë invoer.",
        "solution": """def median_value(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
""",
        "tests": """assert median_value([]) is None
assert median_value([7]) == 7
assert median_value([9, 1, 5]) == 5
assert median_value([1, 8, 3, 6]) == 4.5
items = [3, 1, 2]
assert median_value(items) == 2 and items == [3, 1, 2]
""",
        "hint_en": "Handle the empty case first, then average the two central sorted values when the length is even.",
        "hint_af": "Hanteer eers die leë geval en bereken dan die gemiddelde van die twee middelste gesorteerde waardes wanneer die lengte ewe is.",
        "why_en": "Sorting a copy preserves the input. Odd lengths have one middle item; even lengths have two.",
        "why_af": "Deur 'n kopie te sorteer bly die invoer onveranderd. Onewe lengtes het een middelitem; ewe lengtes het twee.",
    },
    {
        "id": "py_compress_runs",
        "runtime": "python",
        "buggy": """def compress_runs(text):
    result = []
    for char in text:
        if char != result[-1]:
            result.append(char)
    return ''.join(result)
""",
        "prompt_en": "Collapse consecutive duplicate characters while preserving nonconsecutive repetitions and support empty text.",
        "prompt_af": "Vou opeenvolgende duplikaatkarakters saam, behou nie-opeenvolgende herhalings en ondersteun leë teks.",
        "diagnostic_en": "Indexing result[-1] fails before the first character is appended.",
        "diagnostic_af": "Die gebruik van result[-1] faal voordat die eerste karakter bygevoeg is.",
        "solution": """def compress_runs(text):
    result = []
    for char in text:
        if not result or char != result[-1]:
            result.append(char)
    return ''.join(result)
""",
        "tests": """assert compress_runs('') == ''
assert compress_runs('aaabbcca') == 'abca'
assert compress_runs('abc') == 'abc'
assert compress_runs('ööaa') == 'öa'
""",
        "hint_en": "The previous output character exists only after at least one character has been appended.",
        "hint_af": "Die vorige uitvoerkarakter bestaan eers nadat minstens een karakter bygevoeg is.",
        "why_en": "The output list stores one representative of every completed run, so checking emptiness protects the first iteration.",
        "why_af": "Die uitvoerlys hou een verteenwoordiger van elke lopie; die leegheidstoets beskerm dus die eerste iterasie.",
    },
    {
        "id": "py_paginate",
        "runtime": "python",
        "buggy": """def page(items, number, size):
    start = number * size
    return items[start:start + size]
""",
        "prompt_en": "Use one-based page numbers, return a new list, and raise ValueError when number or size is not positive.",
        "prompt_af": "Gebruik bladsynommers wat by een begin, gee 'n nuwe lys terug en gooi ValueError wanneer number of size nie positief is nie.",
        "diagnostic_en": "The start offset treats page numbers as zero-based and invalid arguments are accepted.",
        "diagnostic_af": "Die beginafset behandel bladsynommers as nulgebaseer en ongeldige argumente word aanvaar.",
        "solution": """def page(items, number, size):
    if number <= 0 or size <= 0:
        raise ValueError('number and size must be positive')
    start = (number - 1) * size
    return list(items[start:start + size])
""",
        "tests": """assert page([1, 2, 3, 4, 5], 1, 2) == [1, 2]
assert page([1, 2, 3, 4, 5], 3, 2) == [5]
assert page([1], 2, 3) == []
for args in [([1], 0, 1), ([1], 1, 0)]:
    try:
        page(*args)
        raise AssertionError('ValueError expected')
    except ValueError:
        pass
""",
        "hint_en": "For a one-based page, page 1 starts at index 0, so subtract one before multiplying by the size.",
        "hint_af": "Vir 'n eengebaseerde bladsy begin bladsy 1 by indeks 0; trek dus een af voordat jy met die grootte vermenigvuldig.",
        "why_en": "The offset invariant is (page_number - 1) times page_size. Slicing naturally returns a short or empty final page.",
        "why_af": "Die afsetinvariant is (bladsynommer - 1) maal bladsygrootte. Snywerk gee vanself 'n kort of leë laaste bladsy.",
    },
    {
        "id": "py_parse_sensor",
        "runtime": "python",
        "buggy": """def parse_reading(text):
    value = float(text)
    return value
""",
        "prompt_en": "Trim whitespace, accept an optional trailing C, reject non-finite readings, and raise ValueError for invalid input.",
        "prompt_af": "Verwyder omliggende spasies, aanvaar 'n opsionele C aan die einde, verwerp nie-eindige lesings en gooi ValueError vir ongeldige invoer.",
        "diagnostic_en": "The unit suffix is not removed and float accepts NaN and infinity.",
        "diagnostic_af": "Die eenheidsagtervoegsel word nie verwyder nie en float aanvaar NaN en oneindigheid.",
        "solution": """import math

def parse_reading(text):
    if not isinstance(text, str):
        raise ValueError('reading must be text')
    cleaned = text.strip()
    if cleaned.lower().endswith('c'):
        cleaned = cleaned[:-1].strip()
    try:
        value = float(cleaned)
    except (TypeError, ValueError) as error:
        raise ValueError('invalid reading') from error
    if not math.isfinite(value):
        raise ValueError('reading must be finite')
    return value
""",
        "tests": """assert parse_reading(' 21.5C ') == 21.5
assert parse_reading('-2') == -2.0
for value in ['', 'NaN', 'inf', None]:
    try:
        parse_reading(value)
        raise AssertionError('ValueError expected')
    except ValueError:
        pass
""",
        "hint_en": "Normalize the optional suffix before conversion, then use math.isfinite on the parsed value.",
        "hint_af": "Normaliseer die opsionele agtervoegsel voor omskakeling en gebruik daarna math.isfinite op die geparste waarde.",
        "why_en": "Parsing and validation are separate: successful float conversion does not guarantee a finite sensor reading.",
        "why_af": "Partering en validering is apart: suksesvolle float-omskakeling waarborg nie 'n eindige sensorlesing nie.",
    },
    {
        "id": "py_rolling_average",
        "runtime": "python",
        "buggy": """def rolling_average(values, width):
    return [sum(values[i:i + width]) / width for i in range(len(values))]
""",
        "prompt_en": "Return averages only for complete windows and raise ValueError for a nonpositive width.",
        "prompt_af": "Gee gemiddeldes net vir volledige vensters terug en gooi ValueError vir 'n nie-positiewe width.",
        "diagnostic_en": "The loop includes incomplete suffix windows but still divides them by the full width.",
        "diagnostic_af": "Die lus sluit onvolledige eindvensters in maar deel hulle steeds deur die volle breedte.",
        "solution": """def rolling_average(values, width):
    if width <= 0:
        raise ValueError('width must be positive')
    return [sum(values[i:i + width]) / width for i in range(len(values) - width + 1)]
""",
        "tests": """assert rolling_average([], 2) == []
assert rolling_average([1, 2], 3) == []
assert rolling_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]
try:
    rolling_average([1], 0)
    raise AssertionError('ValueError expected')
except ValueError:
    pass
""",
        "hint_en": "A complete window can start only through index len(values) - width.",
        "hint_af": "'n Volledige venster kan slegs tot by indeks len(values) - width begin.",
        "why_en": "The start range counts exactly n - width + 1 complete windows and becomes empty when the width exceeds the data length.",
        "why_af": "Die beginreeks tel presies n - width + 1 volledige vensters en word leeg wanneer die breedte groter as die data is.",
    },
    {
        "id": "py_nearest_station",
        "runtime": "python",
        "buggy": """def nearest_station(stations, position):
    return min(stations, key=lambda station: station['distance'] - position)
""",
        "prompt_en": "Return None for no stations and choose the station whose numeric distance is closest to position without mutating the input.",
        "prompt_af": "Gee None terug wanneer daar geen stasies is nie en kies die stasie waarvan die numeriese afstand die naaste aan position is sonder om die invoer te verander.",
        "diagnostic_en": "Signed subtraction favors large negative differences instead of the smallest absolute difference.",
        "diagnostic_af": "Getekende aftrekking bevoordeel groot negatiewe verskille in plaas van die kleinste absolute verskil.",
        "solution": """def nearest_station(stations, position):
    if not stations:
        return None
    return min(stations, key=lambda station: abs(float(station['distance']) - position))
""",
        "tests": """assert nearest_station([], 4) is None
stations = [{'name': 'A', 'distance': '2'}, {'name': 'B', 'distance': 7}]
assert nearest_station(stations, 6)['name'] == 'B'
assert nearest_station(stations, 3)['name'] == 'A'
assert stations[0]['distance'] == '2'
""",
        "hint_en": "Closeness depends on the magnitude of the difference, not its sign.",
        "hint_af": "Nabyheid hang van die grootte van die verskil af, nie van die teken daarvan nie.",
        "why_en": "Absolute distance is nonnegative, so min selects the genuinely closest station on either side of the position.",
        "why_af": "Absolute afstand is nie-negatief; min kies dus die werklik naaste stasie aan weerskante van die posisie.",
    },
    {
        "id": "js_total_cost",
        "runtime": "javascript",
        "buggy": """function totalCost(items) {
  return items.reduce((total, item) => total + item.price * item.quantity);
}
""",
        "prompt_en": "Return 0 for an empty array, accept numeric strings, reject non-finite values with TypeError, and do not mutate items.",
        "prompt_af": "Gee 0 vir 'n leë skikking terug, aanvaar numeriese stringe, verwerp nie-eindige waardes met TypeError en moenie items verander nie.",
        "diagnostic_en": "reduce has no initial value and the fields are not explicitly converted or validated.",
        "diagnostic_af": "reduce het geen beginwaarde nie en die velde word nie uitdruklik omgeskakel of gevalideer nie.",
        "solution": """function totalCost(items) {
  return items.reduce((total, item) => {
    const price = Number(item.price);
    const quantity = Number(item.quantity);
    if (!Number.isFinite(price) || !Number.isFinite(quantity)) {
      throw new TypeError('price and quantity must be finite numbers');
    }
    return total + price * quantity;
  }, 0);
}
""",
        "tests": """const assert = require('node:assert/strict');
assert.equal(totalCost([]), 0);
assert.equal(totalCost([{price: '2.5', quantity: 2}, {price: 1, quantity: '3'}]), 8);
assert.throws(() => totalCost([{price: 'x', quantity: 1}]), TypeError);
const items = [{price: '2', quantity: 1}];
totalCost(items);
assert.equal(items[0].price, '2');
""",
        "hint_en": "Give reduce an initial numeric accumulator and validate Number(...) conversions with Number.isFinite.",
        "hint_af": "Gee reduce 'n numeriese beginakkumulator en valideer Number(...)-omskakelings met Number.isFinite.",
        "why_en": "An explicit zero handles empty input and prevents the first object from becoming the accumulator.",
        "why_af": "'n Uitdruklike nul hanteer leë invoer en keer dat die eerste objek die akkumulator word.",
    },
    {
        "id": "js_find_by_code",
        "runtime": "javascript",
        "buggy": """function findByCode(items, code) {
  const index = items.findIndex(item => item.code === code);
  return index ? items[index] : null;
}
""",
        "prompt_en": "Return the matching object, including a match at index zero, and return null when absent.",
        "prompt_af": "Gee die ooreenstemmende objek terug, ook wanneer dit by indeks nul is, en gee null terug wanneer dit afwesig is.",
        "diagnostic_en": "Index zero is falsy while the absent sentinel -1 is truthy.",
        "diagnostic_af": "Indeks nul is vals in 'n voorwaardelike toets terwyl die afwesige sentinelwaarde -1 waar is.",
        "solution": """function findByCode(items, code) {
  const index = items.findIndex(item => item.code === code);
  return index === -1 ? null : items[index];
}
""",
        "tests": """const assert = require('node:assert/strict');
const items = [{code: 'A'}, {code: 'B'}];
assert.equal(findByCode(items, 'A'), items[0]);
assert.equal(findByCode(items, 'B'), items[1]);
assert.equal(findByCode(items, 'X'), null);
""",
        "hint_en": "Compare findIndex's result explicitly with its not-found sentinel instead of testing truthiness.",
        "hint_af": "Vergelyk findIndex se resultaat uitdruklik met sy nie-gevind-sentinelwaarde in plaas daarvan om waarheidswaarde te toets.",
        "why_en": "findIndex returns -1 only for absence; every index from zero upward is valid.",
        "why_af": "findIndex gee net -1 vir afwesigheid terug; elke indeks vanaf nul is geldig.",
    },
    {
        "id": "js_count_available",
        "runtime": "javascript",
        "buggy": """function countAvailable(items) {
  let count = 0;
  for (const item in items) {
    if (item.available) count += 1;
  }
  return count;
}
""",
        "prompt_en": "Count array elements whose available property is exactly true.",
        "prompt_af": "Tel skikkingselemente waarvan die available-eienskap presies true is.",
        "diagnostic_en": "for...in iterates string indexes, not the item objects.",
        "diagnostic_af": "for...in itereer oor stringindekse, nie oor die item-objekte nie.",
        "solution": """function countAvailable(items) {
  let count = 0;
  for (const item of items) {
    if (item.available === true) count += 1;
  }
  return count;
}
""",
        "tests": """const assert = require('node:assert/strict');
assert.equal(countAvailable([]), 0);
assert.equal(countAvailable([{available: true}, {available: false}, {available: true}]), 2);
assert.equal(countAvailable([{available: 1}, {}]), 0);
""",
        "hint_en": "Use the array iteration form that yields values rather than property names.",
        "hint_af": "Gebruik die skikking-iterasievorm wat waardes lewer eerder as eienskapname.",
        "why_en": "for...of yields each object, and strict equality avoids treating unrelated truthy values as booleans.",
        "why_af": "for...of lewer elke objek en streng gelykheid keer dat ander waarheidagtige waardes as booleans tel.",
    },
    {
        "id": "js_chunk_array",
        "runtime": "javascript",
        "buggy": """function chunkArray(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.splice(index, size));
  }
  return chunks;
}
""",
        "prompt_en": "Return consecutive copied chunks including a short final chunk, reject nonpositive sizes, and keep the input unchanged.",
        "prompt_af": "Gee opeenvolgende gekopieerde blokke terug, insluitend 'n kort laaste blok, verwerp nie-positiewe groottes en hou die invoer onveranderd.",
        "diagnostic_en": "splice mutates and shortens the input while the loop index continues to increase.",
        "diagnostic_af": "splice verander en verkort die invoer terwyl die lusindeks aanhou toeneem.",
        "solution": """function chunkArray(items, size) {
  if (!Number.isInteger(size) || size <= 0) {
    throw new RangeError('size must be a positive integer');
  }
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}
""",
        "tests": """const assert = require('node:assert/strict');
const items = [1, 2, 3, 4, 5];
assert.deepEqual(chunkArray(items, 2), [[1, 2], [3, 4], [5]]);
assert.deepEqual(items, [1, 2, 3, 4, 5]);
assert.deepEqual(chunkArray([], 3), []);
assert.throws(() => chunkArray([1], 0), RangeError);
""",
        "hint_en": "Use the nonmutating range-copy method and validate size before entering the loop.",
        "hint_af": "Gebruik die nie-veranderende reeks-kopieermetode en valideer size voordat die lus begin.",
        "why_en": "slice copies each half-open range, so the input length and indexes remain stable.",
        "why_af": "slice kopieer elke half-oop reeks; die invoerlengte en indekse bly dus stabiel.",
    },
    {
        "id": "js_retry_delays",
        "runtime": "javascript",
        "buggy": """function retryDelays(attempts, base) {
  return Array.from({length: attempts}, (_, index) => base * 2 ** (index + 1));
}
""",
        "prompt_en": "Return attempts exponential delays beginning with base, and reject negative attempts or a negative base.",
        "prompt_af": "Gee attempts eksponensiële vertragings terug wat met base begin, en verwerp negatiewe attempts of 'n negatiewe base.",
        "diagnostic_en": "The exponent starts at one, so every delay is doubled one step too early.",
        "diagnostic_af": "Die eksponent begin by een; elke vertraging word dus een stap te vroeg verdubbel.",
        "solution": """function retryDelays(attempts, base) {
  if (!Number.isInteger(attempts) || attempts < 0 || !Number.isFinite(base) || base < 0) {
    throw new RangeError('attempts and base must be nonnegative');
  }
  return Array.from({length: attempts}, (_, index) => base * 2 ** index);
}
""",
        "tests": """const assert = require('node:assert/strict');
assert.deepEqual(retryDelays(0, 100), []);
assert.deepEqual(retryDelays(4, 100), [100, 200, 400, 800]);
assert.throws(() => retryDelays(-1, 100), RangeError);
assert.throws(() => retryDelays(2, -1), RangeError);
""",
        "hint_en": "The first element uses exponent zero because any nonzero base multiplied by 2**0 stays unchanged.",
        "hint_af": "Die eerste element gebruik eksponent nul omdat enige nie-nul basis maal 2**0 onveranderd bly.",
        "why_en": "The index already represents the number of doublings, so adding one causes an off-by-one error.",
        "why_af": "Die indeks verteenwoordig reeds die aantal verdubbelings; om een by te tel veroorsaak 'n een-af-fout.",
    },
    {
        "id": "js_parse_percentage",
        "runtime": "javascript",
        "buggy": """function parsePercentage(text) {
  return parseFloat(text) / 100;
}
""",
        "prompt_en": "Accept strings ending in %, trim whitespace, reject trailing junk and non-finite values, and return the decimal ratio.",
        "prompt_af": "Aanvaar stringe wat op % eindig, verwyder omliggende spasies, verwerp agterste rommel en nie-eindige waardes, en gee die desimale verhouding terug.",
        "diagnostic_en": "parseFloat accepts a numeric prefix and silently ignores invalid trailing characters.",
        "diagnostic_af": "parseFloat aanvaar 'n numeriese voorvoegsel en ignoreer ongeldige agterste karakters stilweg.",
        "solution": """function parsePercentage(text) {
  if (typeof text !== 'string') throw new TypeError('percentage must be text');
  const match = text.trim().match(/^([+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+))%$/);
  if (!match) throw new TypeError('invalid percentage');
  const value = Number(match[1]);
  if (!Number.isFinite(value)) throw new TypeError('percentage must be finite');
  return value / 100;
}
""",
        "tests": """const assert = require('node:assert/strict');
assert.equal(parsePercentage('25%'), 0.25);
assert.equal(parsePercentage(' 12.5% '), 0.125);
assert.equal(parsePercentage('-5%'), -0.05);
assert.throws(() => parsePercentage('20%off'), TypeError);
assert.throws(() => parsePercentage('NaN%'), TypeError);
""",
        "hint_en": "Validate the entire trimmed string with an anchored pattern before converting the captured numeric part.",
        "hint_af": "Valideer die hele gesnoeide string met 'n geankerde patroon voordat die vasgevangde numeriese deel omgeskakel word.",
        "why_en": "Anchors require every input character to match, unlike parseFloat's permissive prefix parsing.",
        "why_af": "Ankers vereis dat elke invoerkarakter pas, anders as parseFloat se toegeeflike voorvoegselpartering.",
    },
]
