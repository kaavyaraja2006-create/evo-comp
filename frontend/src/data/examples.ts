export interface ExampleProgram {
  id: string;
  label: string;
  source: string;
}

// These are example INPUT programs only. Selecting one just populates
// the editor — the lexer still runs for real against whatever text is
// in the editor when LEXICAL ANALYZE is pressed.
export const EXAMPLE_PROGRAMS: ExampleProgram[] = [
  {
    id: "loop-sum",
    label: "Loop & accumulate",
    source: `int main() {
    int total = 0;

    for(int i = 0; i < 10; i++) {
        total = total + i;
    }

    print(total);
}
`,
  },
  {
    id: "simple-add",
    label: "Simple addition",
    source: `int main() {
    int a = 10;
    int b = 20;
    int result = a + b;

    print(result);
}
`,
  },
  {
    id: "function-decl",
    label: "Function declaration",
    source: `function calculate(int x, int y) {
    int result = x * y;
    return result;
}
`,
  },
  {
    id: "mixed-types",
    label: "Mixed types & comments",
    source: `// Computes a discounted price
float price = 99.50;
bool onSale = true;
string label = "Autumn Sale";

if (onSale && price >= 50.0) {
    price = price - 10.0;
} else {
    price = price;
}

print(label);
print(price);
`,
  },
  {
    id: "lexical-error",
    label: "Invalid character (error demo)",
    source: `int total = 10 @ 5;
print(total);
`,
  },
];
