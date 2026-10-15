# Feature reference

Everything holo-convert has to carry through, in one document: inline
marks, lists, tables, code, maths, images, links, breaks - and the
characters the pre-passes rewrite: arrows →, dashes — and ticks ✓, and a
wikilink to \[\[Other note|a label\]\] or \[\[Plain
target#a-heading\]\].

## Text

Plain, *emphasis*, **strong**, ***both***, <s>strike</s>, `inline code`,
<sup>super</sup>, <sub>sub</sub>, a footnote[1], an [external
link](https://example.org), and an [internal link](#tables). A [broken
anchor](#nowhere-at-all) and a near miss to [the tables](#tabels).

> A block quote, with **strong** text inside.

- ☐ an open task
- ☒ a done task

1.  first
2.  second
    - nested bullet
    - another

**A label, then a list with no blank line between:** - first, as GitHub
renders it - second - nested

Term  
Its definition.

## Tables

<table>
<colgroup>
<col style="width: 28%" />
<col style="width: 38%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr class="header">
<th>Left</th>
<th>Centre</th>
<th>Right</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td>ab</td>
<td><code>x</code></td>
<td>1.5</td>
</tr>
<tr class="even">
<td>a very long cell that has to wrap across the column width when
rendered</td>
<td>mid</td>
<td>2</td>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr class="header">
<th>Identifier</th>
<th>Meaning</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td><code>converter-services-2026-10-10</code></td>
<td>a long identifier in the first column</td>
</tr>
<tr class="even">
<td><code>x</code></td>
<td>short</td>
</tr>
</tbody>
</table>

## Code

    def f(x):
        # arrows → and dashes — and ticks ✓ stay as they are in code
        return x ** 2  # “quotes”, ≈
    graph LR
      A --> B

## Maths

Inline *e*<sup>*i**π*</sup> + 1 = 0 and display:

$$\sum\_{k = 1}^{n}k = \frac{n(n + 1)}{2}$$

## Images

<img src="./output/media/generated/media/rId26.svg"
style="width:1.25in;height:0.625in" alt="A vector diagram" />

A vector diagram

<img src="./output/media/generated/media/rId30.png" title="A title"
style="width:0.22222in;height:0.22222in" alt="A small picture" />

A small picture

Line one  
line two, after a hard break.

## After a page break

The end.

[1] The footnote, with `code`.
