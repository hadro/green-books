#!/usr/bin/env node
// Unit tests for gb-matching.js — the address-signature resolver shared by the
// explorers. No dependencies; run with `node tests/matching_test.js`.
//
// gb-matching.js declares bare globals for <script> loading, so it is evaluated
// in a vm context rather than required.
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const SRC = path.join(__dirname, "..", "gb-matching.js");
const ctx = { performance: { now: () => Date.now() } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(SRC, "utf8"), ctx);

let failed = 0;
function check(label, actual, expected) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log(`  ok    ${label}`); return; }
  failed++;
  console.log(`  FAIL  ${label}\n          expected ${e}\n          actual   ${a}`);
}

// Street tokens for an address, sorted for stable comparison.
const streets = (addr, city = "Birmingham", state = "ALABAMA") =>
  [...ctx.gbParseAddress(addr, city, state).streets].sort();

console.log("\ngbParseAddress — trailing directionals must not change the signature");
// Regression: the $-anchored STREET_SUFFIXES strip cannot fire when a
// directional trails the street type, so "Ave" used to survive as a token and
// the bare ordinal every other spelling produces was never minted. One business
// (the A. G. Gaston Motel, 1510 5th Ave. N., Birmingham) was split across three
// groups by this alone.
for (const addr of [
  "1510 5th Ave.",
  "1510 5th Ave. N.",
  "1510 5th Ave., N.",
  "1510 5th Ave. No.",
  "1510 5th Avenue North",
  "1510 Fifth Ave. N",
  "1510 Fifth Avenue, N. W.",
]) check(addr, streets(addr), ["5"]);

console.log("\ngbParseAddress — a directional run with no space still strips");
check("241 Auburn Ave. N.E", streets("241 Auburn Ave. N.E", "Atlanta", "GEORGIA"), ["auburn"]);
check("241 Auburn Ave. N. E.", streets("241 Auburn Ave. N. E.", "Atlanta", "GEORGIA"), ["auburn"]);

console.log("\ngbParseAddress — streets NAMED for a direction keep their name");
// Brooklyn's "Avenue S" and Washington's lettered streets have no street name
// left once the trailing directional goes, so the strip must fall back.
check('501 Ave. S.', streets("501 Ave. S.", "Brooklyn", "NEW YORK"), ["ave"]);
check('4106 Ave. N.', streets("4106 Ave. N.", "Brooklyn", "NEW YORK"), ["ave"]);
check('1435 "Q" St. N. W.', streets('1435 "Q" St. N. W.', "Washington", "D.C."), ["qst"]);
check('1102 U St. N. W.', streets("1102 U St. N. W.", "Washington", "D.C."), ["ust"]);
check('1207 So. "M" St.', streets('1207 So. "M" St.', "Tacoma", "WASHINGTON"), ["som"]);

console.log("\ngbParseAddress — established behaviour that must not drift");
check("named street", streets("1510 Willis Ave."), ["willis"]);
check("ordinal canonicalized", streets("1510 W. 125th St."), ["125"]);
check("spelled ordinal", streets("1510 Seventh Ave."), ["7"]);
check("spacing variant", streets("22 La Salle St.", "Chicago", "ILLINOIS"), ["lasalle", "salle"]);
check("half address", streets("6001/2 E. Washington St.", "High Point", "N. C."), ["washington"]);
check("intersection", streets("7th Ave. at 125th St."), ["125", "7"]);
check("placeholder is not an address", streets("not specified"), []);
check("city/state words dropped", streets("New York, N. Y.", "New York", "NEW YORK"), []);

console.log("\ngbHouseRange — frontage ranges expand, ordinals and wide spans do not");
const range = s => { const r = ctx.gbHouseRange(s); return r ? [...r].sort((a, b) => a - b) : null; };
check("306-8", range("306-8 WEST 143rd STREET"), [306, 307, 308]);
check("1502 - 13TH ST is not a range", range("1502 - 13TH ST., N. W."), null);
check("span cap", range("100-900 Broadway"), null);

console.log("\ngbBuildMatchIndex — one business, one address, many spellings");
// The real A. G. Gaston Motel rows, Birmingham. The two name forms bucket
// separately (gbNewNameStem runs before address resolution), so 2 groups is
// correct here; 3 was the bug.
const gaston = [
  ["A. G. Gaston's Motel", "1510 5th Avenue North"],
  ["A. G. Gaston Motel", "1510 5th Avenue North"],
  ["A. G. Gaston Motel", "1510 Fifth Ave. N"],
  ["A. G. Gaston Motel", "1510 5th Ave. No."],
  ["A. G. Gaston Motel", "1510 5th Ave., N."],
  ["A. G. Gaston Motel", "1510 - 5th Ave. No., Birmingham, Ala."],
  ["Gaston, A. G. (Motel)", "1510 5th Ave., N."],
].map(([name, address]) => ({ name, address, city: "Birmingham", state: "ALABAMA" }));
const { rowToKey } = ctx.gbBuildMatchIndex(gaston);
check("groups", new Set(gaston.map(r => rowToKey.get(r))).size, 2);
check("all six spellings of one name form share a group",
  new Set(gaston.slice(0, 6).map(r => rowToKey.get(r))).size, 1);

console.log(failed ? `\n${failed} test(s) failed\n` : "\nall tests passed\n");
process.exit(failed ? 1 : 0);
