# Targets

Targets decide which receivers a notification goes to. You can target
people, areas and receivers, in any combination.

## Kinds of target

- **People**: receivers associated with everyone (any person), or with any
  of the individuals you list, as chosen in the
  [action](services.md#people). See
  [receiver person](next-steps/person.md).
- **Areas**: receivers whose device is in any of the listed areas. A
  receiver's area is the area of its device in Home Assistant (see
  [receiver areas](next-steps/areas.md)).
- **Receivers**: receivers named explicitly, or every receiver with an area
  (**All Areas**).

The results are combined as a **union**: a receiver is used if it matches
any listed person, any listed area, or is named. A receiver that matches in
more than one way is used once.

## A group that is not given is not targeted

Each group is targeted only when you give it. If you leave out people, no
person is targeted: a receiver with a person is reached only if it also
falls under a targeted area or is named. The same goes for receivers and
areas. There is no default; with no targets at all nothing is reached, and
the action reports an error.

## Which receivers are reached

A receiver is used when it is assigned to a targeted person, or targeted
through the receivers target. A receiver with no person and no area is only
used when it is named (or reached through its device or a label).

- **Everyone** reaches every receiver that has a person. **All Areas**
  reaches every receiver that has an area.
- A receiver with no area is never reached by an area or floor target, and
  one with no person is never reached by a person target.
- The **persistent notification** receiver cannot have a person. It starts
  with no area, so it is only used when named. Give its device an area and
  area targets reach it like any other receiver.
- Unknown people, areas and receivers match nothing.

## Disabled receivers

Only receivers whose **enabled** switch is on are notified, however they
were targeted. A matching receiver that is disabled, including one named
explicitly, is skipped and reported as skipped. A receiver that is not
loaded counts as disabled.

## Conditions

After targeting and the enabled check, each receiver's
[conditions](conditions.md) are evaluated; one that does not pass is
skipped for that notification.

## Seeing a receiver's targets

The [Receivers](next-steps/dashboard.md#receivers) page shows the person and
area of each receiver as badges.
