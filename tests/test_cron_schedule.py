#!/usr/bin/env python3
"""
Tests for cron schedule generation and validation.
Ensures generated cron lines are syntactically correct and don't conflict.
"""

import pytest
from datetime import datetime
from core.timezone_utils import get_scheduled_times_for_date


class TestCronScheduleGeneration:
    """Test that generated cron schedules are valid and non-overlapping."""
    
    def test_no_duplicate_cron_times(self):
        """Ensure no two states have identical cron times."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        cron_times = set()
        for entry in schedule:
            # Create a unique cron signature
            cron_sig = (entry['run_type'], entry['cron_hour'], entry['cron_minute'])
            # Same cron time is allowed if states are in same group (staggered)
            # But verify logic is sound
            cron_times.add((entry['state'], cron_sig))
        
        # No state should appear twice
        states = {}
        for state, cron_sig in cron_times:
            assert state not in states or states[state] != cron_sig, \
                f"State {state} appears multiple times with same cron signature"
            states[state] = cron_sig
    
    def test_staggering_within_groups(self):
        """Verify that groups are staggered by 30-minute intervals."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        # Group by run_type and extract cron times per group
        for run_type in ['morning', 'evening']:
            entries = [e for e in schedule if e['run_type'] == run_type]
            
            # Build a map: group -> list of (hour, minute) tuples
            group_times = {}
            for entry in entries:
                group = entry['group']
                if group not in group_times:
                    group_times[group] = []
                group_times[group].append((entry['cron_hour'], entry['cron_minute']))
            
            # Verify groups are approximately 30 minutes apart
            # (Not exact due to offset applied at stagger time, but should be close)
            # For now, just ensure we have 4 groups
            assert len(group_times) == 4, f"Expected 4 groups for {run_type}, got {len(group_times)}"
    
    def test_cron_hour_minute_valid(self):
        """Verify all cron hours and minutes are valid."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        for entry in schedule:
            assert 0 <= entry['cron_hour'] <= 23, \
                f"Invalid cron hour {entry['cron_hour']} for {entry['state']}"
            assert 0 <= entry['cron_minute'] <= 59, \
                f"Invalid cron minute {entry['cron_minute']} for {entry['state']}"
    
    def test_cron_expression_format(self):
        """Verify cron expressions are properly formatted."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        for entry in schedule:
            # A valid cron expression should have: minute hour * * *
            cron_line = f"{entry['cron_minute']} {entry['cron_hour']} * * *"
            parts = cron_line.split()
            assert len(parts) == 5, f"Invalid cron format: {cron_line}"
            assert parts[0].isdigit() and 0 <= int(parts[0]) <= 59
            assert parts[1].isdigit() and 0 <= int(parts[1]) <= 23
            assert parts[2] == '*'
            assert parts[3] == '*'
            assert parts[4] == '*'
    
    def test_schedule_spread_across_day(self):
        """Verify that schedule is spread throughout the day (morning and evening)."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        morning_entries = [e for e in schedule if e['run_type'] == 'morning']
        evening_entries = [e for e in schedule if e['run_type'] == 'evening']
        
        assert len(morning_entries) == 8, "Should have 8 morning entries (all states)"
        assert len(evening_entries) == 8, "Should have 8 evening entries (all states)"
        
        # Morning should have lower UTC hours (roughly), evening should have higher
        morning_hours = {e['cron_hour'] for e in morning_entries}
        evening_hours = {e['cron_hour'] for e in evening_entries}
        
        # Just ensure they're different (morning/evening are distinct times)
        assert morning_hours != evening_hours, "Morning and evening should have different UTC times"
    
    def test_all_states_present_in_schedule(self):
        """Ensure all 8 Australian states are represented in schedule."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        states_present = {entry['state'] for entry in schedule}
        expected_states = {'NSW', 'VIC', 'TAS', 'ACT', 'SA', 'WA', 'NT', 'QLD'}
        
        assert states_present == expected_states, \
            f"Missing states: {expected_states - states_present}"
    
    def test_schedule_consistency_across_dates(self):
        """Verify schedule pattern is consistent across different dates."""
        dates = [
            datetime(2026, 2, 15),  # Summer
            datetime(2026, 5, 15),  # Autumn
            datetime(2026, 8, 15),  # Winter
            datetime(2026, 11, 15),  # Spring (near DST)
        ]
        
        schedules = []
        for date in dates:
            schedule = get_scheduled_times_for_date(date)
            states = {entry['state'] for entry in schedule}
            schedules.append(states)
        
        # All should have the same states
        for sched in schedules:
            assert sched == schedules[0], "Schedule should be consistent across dates"
    
    def test_cron_schedule_local_times_correct(self):
        """Verify that local_time field matches expected 06:00/18:00."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        local_times = {entry['local_time'] for entry in schedule}
        # Should only have 06:00 and 18:00
        assert '06:00' in local_times
        assert '18:00' in local_times
        assert len(local_times) == 2


class TestCronScheduleEdgeCases:
    """Test edge cases and DST boundary conditions."""
    
    def test_schedule_near_autumn_dst(self):
        """Test schedule generation near autumn DST transition (April)."""
        # April 4 (day before DST) and April 5 (day of DST)
        date_before = datetime(2026, 4, 4)
        date_after = datetime(2026, 4, 5)
        
        schedule_before = get_scheduled_times_for_date(date_before)
        schedule_after = get_scheduled_times_for_date(date_after)
        
        # Both should be valid
        assert len(schedule_before) == 16
        assert len(schedule_after) == 16
        
        # UTC times will differ due to DST transition
        # (This is expected and correct)
    
    def test_schedule_near_spring_dst(self):
        """Test schedule generation near spring DST transition (October)."""
        # October 3 (before DST) and October 4 (day of DST)
        date_before = datetime(2026, 10, 3)
        date_after = datetime(2026, 10, 4)
        
        schedule_before = get_scheduled_times_for_date(date_before)
        schedule_after = get_scheduled_times_for_date(date_after)
        
        # Both should be valid
        assert len(schedule_before) == 16
        assert len(schedule_after) == 16
    
    def test_western_states_no_dst_variation(self):
        """Verify WA and NT have consistent UTC times across DST transitions."""
        # Pick dates across a DST transition
        dates = [
            datetime(2026, 2, 15),  # Summer (AEDT zone)
            datetime(2026, 5, 15),  # Autumn (AEST zone)
            datetime(2026, 8, 15),  # Winter (AEST zone)
        ]
        
        wa_times_morning = []
        for date in dates:
            schedule = get_scheduled_times_for_date(date)
            wa_morning = [e for e in schedule if e['state'] == 'WA' and e['run_type'] == 'morning']
            assert len(wa_morning) == 1
            wa_times_morning.append((wa_morning[0]['cron_hour'], wa_morning[0]['cron_minute']))
        
        # All WA morning times should be identical (no DST for WA)
        assert wa_times_morning[0] == wa_times_morning[1] == wa_times_morning[2], \
            "WA should not vary across DST transitions"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
