"""
Tests for the Mergington High School API
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Save original state
    original_activities = {}
    for name, details in activities.items():
        original_activities[name] = {
            **details,
            "participants": details["participants"].copy()
        }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        activities[name]["participants"] = details["participants"]


class TestRootEndpoint:
    def test_root_redirect(self, client):
        """Test that root redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestActivitiesEndpoint:
    def test_get_all_activities(self, client):
        """Test getting all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check that required activities are present
        assert "Basketball Team" in data
        assert "Soccer Club" in data
        assert "Chess Club" in data
        assert "Programming Class" in data
    
    def test_activity_structure(self, client):
        """Test that activities have required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            assert "description" in activity_details
            assert "schedule" in activity_details
            assert "max_participants" in activity_details
            assert "participants" in activity_details
            assert isinstance(activity_details["participants"], list)
    
    def test_activities_have_initial_participants(self, client):
        """Test that some activities have initial participants"""
        response = client.get("/activities")
        data = response.json()
        
        # Chess Club should have michael and daniel
        assert "michael@mergington.edu" in data["Chess Club"]["participants"]
        assert "daniel@mergington.edu" in data["Chess Club"]["participants"]
        
        # Programming Class should have emma and sophia
        assert "emma@mergington.edu" in data["Programming Class"]["participants"]
        assert "sophia@mergington.edu" in data["Programming Class"]["participants"]


class TestSignupEndpoint:
    def test_signup_success(self, client, reset_activities):
        """Test successfully signing up for an activity"""
        email = "newstudent@mergington.edu"
        activity = "Art Club"
        
        response = client.post(
            f"/activities/{activity}/signup?email={email}",
            follow_redirects=False
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data[activity]["participants"]
    
    def test_signup_duplicate_fails(self, client, reset_activities):
        """Test that signing up twice fails"""
        email = "newstudent@mergington.edu"
        activity = "Art Club"
        
        # First signup
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]
    
    def test_signup_nonexistent_activity(self, client):
        """Test signing up for non-existent activity"""
        email = "student@mergington.edu"
        activity = "Nonexistent Club"
        
        response = client.post(f"/activities/{activity}/signup?email={email}")
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_signup_to_full_activity(self, client, reset_activities):
        """Test that cannot signup when activity is full"""
        activity = "Science Club"
        
        # Science Club has max 10 participants
        # First, fill it up
        for i in range(10):
            email = f"student{i}@mergington.edu"
            response = client.post(f"/activities/{activity}/signup?email={email}")
            if i < 10:
                assert response.status_code == 200
        
        # Try to add one more - should fail
        email = "student_extra@mergington.edu"
        response = client.post(f"/activities/{activity}/signup?email={email}")
        assert response.status_code == 400
        assert "no spots available" in response.json()["detail"].lower()


class TestUnregisterEndpoint:
    def test_unregister_success(self, client, reset_activities):
        """Test successfully unregistering from an activity"""
        email = "michael@mergington.edu"
        activity = "Chess Club"
        
        # Verify participant exists
        activities_before = client.get("/activities").json()
        assert email in activities_before[activity]["participants"]
        
        # Unregister
        response = client.post(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 200
        assert "Unregistered" in response.json()["message"]
        
        # Verify participant was removed
        activities_after = client.get("/activities").json()
        assert email not in activities_after[activity]["participants"]
    
    def test_unregister_not_registered(self, client):
        """Test unregistering when not registered fails"""
        email = "notregistered@mergington.edu"
        activity = "Art Club"
        
        response = client.post(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 400
        assert "not registered" in response.json()["detail"]
    
    def test_unregister_nonexistent_activity(self, client):
        """Test unregistering from non-existent activity"""
        email = "student@mergington.edu"
        activity = "Nonexistent Club"
        
        response = client.post(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]


class TestActivityAvailability:
    def test_availability_calculation(self, client):
        """Test that availability is correctly calculated"""
        response = client.get("/activities")
        data = response.json()
        
        # Check activities with known participants
        chess_club = data["Chess Club"]
        assert chess_club["max_participants"] == 12
        assert len(chess_club["participants"]) == 2
        # Availability should be calculated on frontend, but we can verify data integrity
        assert chess_club["max_participants"] >= len(chess_club["participants"])
    
    def test_no_negative_availability(self, client):
        """Test that availability never goes negative"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            available_spots = activity_details["max_participants"] - len(activity_details["participants"])
            assert available_spots >= 0, f"{activity_name} has negative available spots"
