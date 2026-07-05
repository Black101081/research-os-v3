# Alpha Lifecycle States v1

Purpose: define the allowed alpha states and state transitions for Alpha Factory lifecycle control.

## States
- draft
- validated
- promoted
- shadow
- active
- quarantined
- demoted
- retired

## Transition rules
- draft -> validated
- validated -> promoted
- validated -> demoted
- promoted -> shadow
- promoted -> active
- shadow -> active
- shadow -> quarantined
- shadow -> demoted
- active -> quarantined
- active -> demoted
- active -> retired
- quarantined -> active
- quarantined -> retired
- quarantined -> demoted
- demoted -> validated
- demoted -> retired

No direct draft -> active transition is allowed.
No transition out of retired is allowed.
