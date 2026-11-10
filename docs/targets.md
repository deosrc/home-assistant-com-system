# Targets

Targets decide which receivers a notification goes to. You can target
people, areas and receivers, in any combination.

## Kinds of target

- **People**: receivers associated with everyone (any person), or with any
  of the individuals you list, as chosen in the
  [action](services.md#people). A
  receiver's people are set on the receiver (see
  [people and areas](receivers/README.md#people-and-areas)).
- **Areas**: receivers whose device is in any of the listed areas. A
  receiver's area is the area of its device in Home Assistant.
- **Receivers**: receivers named explicitly, or every receiver with an area
  (**All Areas**).

The results are combined as a **union**: a receiver is used if it matches
any listed person, any listed area, or is named. A receiver that matches in
more than one way is used once.

## Default

When no targets are given, the notification goes to **all people and all
areas**: every receiver that is associated with a person or has an area.

## Receivers that are not reached by people or areas

- A **shared** receiver has no person, so a person target never reaches it
  and the default does not include it unless it has an area. Reach it by
  area, or name it.
- A receiver with no area is never reached by an area target.
- The **persistent notification** receiver is system-wide. It is used only
  when named explicitly, even if you give its device an area, and it is not
  part of the default.
- Unknown people, areas and receivers match nothing.

## Disabled receivers

Only receivers whose **enabled** switch is on are notified, however they
were targeted. A matching receiver that is disabled, including one named
explicitly, is skipped and reported as skipped. A receiver that is not
loaded counts as disabled.

## Seeing a receiver's targets

The [Receivers](ui.md#receivers) page shows the person and area of each
receiver as badges.
