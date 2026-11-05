# E27-M01 — Motor Control with Emergency Stop and Reset

## Requirement

The motor shall start when the Start push button is pressed if the emergency-stop circuit is healthy, the Stop push button is not pressed, and no overload fault is present.

The motor shall stop when:
- the Stop push button is pressed,
- the emergency stop is activated, or
- an overload fault occurs.

After an emergency-stop or overload event, the fault shall remain latched. The motor shall not restart until:
1. the safety circuit is healthy again,
2. no overload is active,
3. the Stop push button is released, and
4. Reset is pressed.

## Scope

This is a deliberately restricted Boolean control case for the ElCon-EE 2027 pilot study.
Timers, function blocks, and hardware-specific I/O are excluded from this first case.

## Ground-truth safety intent

A safety trip must force the motor OFF and must prevent automatic restart after the trip clears.
