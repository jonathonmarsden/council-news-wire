#!/usr/bin/env python3
"""
Tests for timezone conversions and cron schedule generation.
Verifies that local times (06:00, 18:00) convert correctly to UTC per state.
Also tests DST transitions (March/October in Australia).
"""

import pytest
import pytz
from datetime import datetime, timedelta
from core.timezone_utils import (
    get_utc_time,
    get_cron_time,
    get_scheduled_times_for_date,
    is_morning_window,
    get_recommended_concurrency,
    STATE_TIMEZONES,
)


class TestTimeZoneConversion:
    """Test basic UTC conversion for all Australian states."""
    
    def test_utc_conversion_eastern(self):
        """Test Eastern states (NSW, VIC, TAS, ACT) conversion to UTC."""
        # During AEDT (summer, e.g., Feb 15, 2026): UTC+11
        test_date = datetime(2026, 2, 15)  # Summer in Australia
        
        # NSW at 06:00 AEDT should be 19:00 UTC previous day
        utc = get_utc_time('NSW', 6, 0, test_date)
        assert utc.hour == 19
        assert utc.day == 14  # Previous day in UTC
        
        # NSW at 18:00 AEDT should be 07:00 UTC same day
        utc = get_utc_time('NSW', 18, 0, test_date)
        assert utc.hour == 7
        assert utc.day == 15
    
    def test_utc_conversion_western(self):
        """Test Western states (WA, NT) conversion to UTC."""
        # WA is UTC+8 year-round (no DST)
        test_date = datetime(2026, 2, 15)
        
        # WA at 06:00 AWST should be 22:00 UTC previous day
        utc = get_utc_time('WA', 6, 0, test_date)
        assert utc.hour == 22
        assert utc.day == 14
        
        # WA at 18:00 AWST should be 10:00 UTC same day
        utc = get_utc_time('WA', 18, 0, test_date)
        assert utc.hour == 10
        assert utc.day == 15
    
    def test_utc_conversion_central(self):
        """Test SA (Central time) conversion to UTC."""
        # During ACDT (summer): UTC+10:30
        test_date = datetime(2026, 2, 15)
        
        # SA at 06:00 ACDT should be 19:30 UTC previous day
        utc = get_utc_time('SA', 6, 0, test_date)
        assert utc.hour == 19
        assert utc.minute == 30
        assert utc.day == 14
    
    def test_dst_transition_autumn(self):
        """Test autumn DST transition (first Sunday in April)."""
        # April 5, 2026 is the autumn (fall back) transition in Australia
        # Before: UTC+11 (AEDT), After: UTC+10 (AEST)
        before_dst = datetime(2026, 4, 4, 6, 0)  # Saturday, AEDT
        after_dst = datetime(2026, 4, 5, 6, 0)   # Sunday, AEST
        
        utc_before = get_utc_time('NSW', 6, 0, before_dst)
        utc_after = get_utc_time('NSW', 6, 0, after_dst)
        
        # Before DST: 06:00 AEDT = 19:00 UTC
        assert utc_before.hour == 19
        
        # After DST: 06:00 AEST = 20:00 UTC (one hour later in UTC)
        assert utc_after.hour == 20
    
    def test_dst_transition_spring(self):
        """Test spring DST transition (first Sunday in October)."""
        # October 4, 2026 is the spring (spring forward) transition
        # Before: UTC+10 (AEST), After: UTC+11 (AEDT)
        before_dst = datetime(2026, 10, 3, 6, 0)  # Saturday, AEST
        after_dst = datetime(2026, 10, 4, 6, 0)   # Sunday, AEDT
        
        utc_before = get_utc_time('NSW', 6, 0, before_dst)
        utc_after = get_utc_time('NSW', 6, 0, after_dst)
        
        # Before DST: 06:00 AEST = 20:00 UTC
        assert utc_before.hour == 20
        
        # After DST: 06:00 AEDT = 19:00 UTC (one hour earlier in UTC)
        assert utc_after.hour == 19
    
    def test_no_dst_western_states(self):
        """Test that WA and NT do not observe DST."""
        summer = datetime(2026, 2, 15)
        winter = datetime(2026, 8, 15)
        
        # WA should have same UTC offset year-round
        utc_summer = get_utc_time('WA', 12, 0, summer)
        utc_winter = get_utc_time('WA', 12, 0, winter)
        
        # Noon local should be 04:00 UTC year-round (UTC+8)
        assert utc_summer.hour == 4
        assert utc_winter.hour == 4
    
    def test_cron_time_tuple(self):
        """Test cron time tuple generation."""
        test_date = datetime(2026, 2, 15)
        
        # NSW 06:00 local = 19:00, 00 min UTC
        cron_hour, cron_minute = get_cron_time('NSW', 6, 0, test_date)
        assert cron_hour == 19
        assert cron_minute == 0
        
        # SA 18:00 local = 07:30 UTC
        cron_hour, cron_minute = get_cron_time('SA', 18, 0, test_date)
        assert cron_hour == 7
        assert cron_minute == 30


class TestScheduleGeneration:
    """Test schedule generation for twice-daily runs."""
    
    def test_scheduled_times_all_states(self):
        """Verify all 8 states appear in schedule."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        # 8 states * 2 runs (morning + evening) = 16 entries
        assert len(schedule) == 16
        
        states = {entry['state'] for entry in schedule}
        expected_states = {'NSW', 'VIC', 'TAS', 'ACT', 'SA', 'WA', 'NT', 'QLD'}
        assert states == expected_states
    
    def test_scheduled_times_grouping(self):
        """Verify states are grouped correctly."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        # Extract groups
        groups = {}
        for entry in schedule:
            run_key = (entry['group'], entry['run_type'])
            if run_key not in groups:
                groups[run_key] = []
            groups[run_key].append(entry['state'])
        
        # Each group should have exactly 2 states
        for group, states in groups.items():
            assert len(states) == 2
    
    def test_scheduled_times_structure(self):
        """Verify schedule entries have all required fields."""
        test_date = datetime(2026, 2, 15)
        schedule = get_scheduled_times_for_date(test_date)
        
        required_fields = {'state', 'group', 'local_time', 'run_type', 'cron_hour', 'cron_minute', 'utc_time'}
        for entry in schedule:
            assert all(field in entry for field in required_fields)
            assert entry['state'] in {'NSW', 'VIC', 'TAS', 'ACT', 'SA', 'WA', 'NT', 'QLD'}
            assert entry['run_type'] in {'morning', 'evening'}
            assert 0 <= entry['cron_hour'] <= 23
            assert 0 <= entry['cron_minute'] <= 59


class TestMorningWindow:
    """Test morning peak detection for dynamic concurrency."""
    
    def test_morning_window_boundaries(self):
        """Test that morning window correctly identifies 06:00-08:30."""
        assert is_morning_window(6, 0)   # Start of window
        assert is_morning_window(7, 15)  # Middle
        assert is_morning_window(8, 30)  # End of window
        assert not is_morning_window(5, 59)  # Just before
        assert not is_morning_window(8, 31)  # Just after
    
    def test_evening_not_in_morning_window(self):
        """Test that evening hours are not in morning window."""
        assert not is_morning_window(18, 0)
        assert not is_morning_window(20, 0)
        assert not is_morning_window(0, 0)


class TestConcurrencyRecommendation:
    """Test dynamic concurrency recommendations."""
    
    def test_high_load_morning(self):
        """High-load states should have reduced concurrency in morning."""
        high_load = ['NSW', 'VIC', 'WA']
        for state in high_load:
            assert get_recommended_concurrency(state, is_morning=True) == 4
            assert get_recommended_concurrency(state, is_morning=False) == 8
    
    def test_medium_load_morning(self):
        """Medium-load states should have reduced concurrency in morning."""
        medium_load = ['QLD', 'SA']
        for state in medium_load:
            assert get_recommended_concurrency(state, is_morning=True) == 3
            assert get_recommended_concurrency(state, is_morning=False) == 6
    
    def test_low_load_morning(self):
        """Low-load states should have reduced concurrency in morning."""
        low_load = ['TAS', 'NT', 'ACT']
        for state in low_load:
            assert get_recommended_concurrency(state, is_morning=True) == 2
            assert get_recommended_concurrency(state, is_morning=False) == 4


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
