# E27-M01 — First ElCon-EE 2027 Pilot Run

## Goal

Confirm that:
1. the reference program compiles,
2. the reset-bypass mutant also compiles,
3. the mutant contains a reachable safety violation,
4. the existing static validator is measured before any repair.

## What to do

### 1. Copy the `research/elcon2027` folder into the root of OptPLC.

### 2. Run the witness simulator

From the case folder:

```bash
python simulate_witness.py
```

Expected development-oracle output:

```text
scan,reference_motor,mutant_m3_motor
1,1,1
2,0,0
3,0,1
```

At scan 3, the reference stays OFF while M-M3 restarts without Reset.

### 3. Compile the reference using the same MATIEC path used by OptPLC

File: `reference.st`

Record exit code, stdout, stderr, and MATIEC version/container image.
Expected: COMPILE PASS.

### 4. Compile the first mutant

File: `mutants/M-M3_reset_bypass.st`
Expected: COMPILE PASS.

If it fails compilation, report the MATIEC output before changing anything.

### 5. Run the existing OptPLC motor-domain/static validator on both files

Do not change validator rules yet.
Record the reference verdict, mutant verdict, and triggered rule IDs.
If the mutant passes, that is useful baseline evidence.

### 6. Fill the JSON result template

Use: `../../results/E27-M01_M-M3_result_TEMPLATE.json`

nuXmv remains NOT_IMPLEMENTED in this first baseline run.
