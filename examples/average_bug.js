function average(values) {
  return values.reduce((sum, value) => sum + value) / values.length;
}

console.log(average([]));
console.log(average(["1", "2", "3"]));
