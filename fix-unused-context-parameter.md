# Fix: Remove Unused Context Parameter from importEventAsSchedule

## Issue
The `context: Any` parameter in `importEventAsSchedule(event:context:)` is not used in the implementation but forces unnecessary dependencies on callers.

## Location
File: `AISecretary/AISecretary/Services/CalendarSyncService.swift`
Function: `importEventAsSchedule(event:context:)`
Line: ~169

## Current Implementation
```swift
/// 外部カレンダーイベントをアプリ内ScheduleItemに変換
func importEventAsSchedule(event: ExternalCalendarEvent, context: Any) -> ScheduleItem {
    ScheduleItem(
        title: "📅 \(event.title)",
        detail: [event.calendarName, event.notes].compactMap { $0 }.joined(separator: "\n"),
        startDate: event.startDate,
        endDate: event.endDate,
        isAllDay: event.isAllDay,
        priority: .normal,
        location: event.location ?? ""
    )
}
```

## Problem
The `context: Any` parameter is:
1. Not used anywhere in the function body
2. Forces callers to pass an unnecessary argument
3. Creates unnecessary coupling
4. The parameter name suggests it might be intended for `ModelContext`, but it's never actually used

## Solution
Remove the unused `context` parameter from the function signature.

## Fixed Implementation
```swift
/// 外部カレンダーイベントをアプリ内ScheduleItemに変換
func importEventAsSchedule(event: ExternalCalendarEvent) -> ScheduleItem {
    ScheduleItem(
        title: "📅 \(event.title)",
        detail: [event.calendarName, event.notes].compactMap { $0 }.joined(separator: "\n"),
        startDate: event.startDate,
        endDate: event.endDate,
        isAllDay: event.isAllDay,
        priority: .normal,
        location: event.location ?? ""
    )
}
```

## Call Sites to Update
Search for all usages of `importEventAsSchedule` and remove the second argument:

```bash
# Find all call sites
grep -r "importEventAsSchedule" --include="*.swift"
```

Typical call site change:
```swift
// Before
let schedule = importEventAsSchedule(event: externalEvent, context: modelContext)

// After
let schedule = importEventAsSchedule(event: externalEvent)
```

## Alternative: If Context is Actually Needed
If the context parameter is needed for future use (e.g., to save the ScheduleItem directly to the database), the function should:
1. Use a concrete type like `ModelContext` instead of `Any`
2. Actually use the parameter in the implementation

```swift
/// 外部カレンダーイベントをアプリ内ScheduleItemに変換して保存
func importEventAsSchedule(event: ExternalCalendarEvent, context: ModelContext) -> ScheduleItem {
    let schedule = ScheduleItem(
        title: "📅 \(event.title)",
        detail: [event.calendarName, event.notes].compactMap { $0 }.joined(separator: "\n"),
        startDate: event.startDate,
        endDate: event.endDate,
        isAllDay: event.isAllDay,
        priority: .normal,
        location: event.location ?? ""
    )
    context.insert(schedule)  // Actually use the context
    return schedule
}
```

However, this changes the function's behavior and should only be done if that's the intended design.

## Recommendation
**Remove the parameter** since it's not used and callers can insert the returned `ScheduleItem` into the context themselves if needed. This follows the Single Responsibility Principle - the function converts the event, and the caller decides what to do with the result.

## Testing
After making the changes:
1. Build the project to ensure no compilation errors
2. Search for any remaining references to the old signature
3. Run existing tests to ensure functionality is preserved
4. Test the calendar sync feature manually if available

## References
- Original issue: https://github.com/mitsu888/cline/pull/2#discussion_r3068620803
- Issue #8: https://github.com/mitsu888/all/issues/8
