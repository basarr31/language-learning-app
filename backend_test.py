#!/usr/bin/env python3

import requests
import sys
import json
import time
from datetime import datetime
import io

class LanguageLearningAPITester:
    def __init__(self, base_url="https://quirky-babbage.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_cards = []

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        
        if files is None:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, data=data)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 200:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, list):
                        print(f"   Response: List with {len(response_data)} items")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response.json() if response.text and response.status_code < 500 else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_create_vocabulary_card(self):
        """Test creating vocabulary cards"""
        # Test French card
        french_card = {
            "word": "bonjour",
            "translation": "hello",
            "example": "Bonjour, comment allez-vous?",
            "notes": "Common greeting",
            "difficulty": "easy",
            "language": "french"
        }
        
        success, response = self.run_test(
            "Create French Vocabulary Card",
            "POST",
            "vocabulary",
            200,
            data=french_card
        )
        
        if success and 'id' in response:
            self.created_cards.append(response['id'])
            print(f"   Created card ID: {response['id']}")
        
        # Test English card
        english_card = {
            "word": "difficult",
            "translation": "difficile",
            "example": "This task is very difficult",
            "notes": "Adjective",
            "difficulty": "medium",
            "language": "english"
        }
        
        success2, response2 = self.run_test(
            "Create English Vocabulary Card",
            "POST",
            "vocabulary",
            200,
            data=english_card
        )
        
        if success2 and 'id' in response2:
            self.created_cards.append(response2['id'])
            print(f"   Created card ID: {response2['id']}")
        
        return success and success2

    def test_get_vocabulary_cards(self):
        """Test retrieving vocabulary cards"""
        # Get all cards
        success1, response1 = self.run_test(
            "Get All Vocabulary Cards",
            "GET",
            "vocabulary",
            200
        )
        
        # Get French cards only
        success2, response2 = self.run_test(
            "Get French Vocabulary Cards",
            "GET",
            "vocabulary?language=french",
            200
        )
        
        # Get specific card if we have one
        if self.created_cards:
            success3, response3 = self.run_test(
                "Get Specific Vocabulary Card",
                "GET",
                f"vocabulary/{self.created_cards[0]}",
                200
            )
            return success1 and success2 and success3
        
        return success1 and success2

    def test_study_endpoints(self):
        """Test study-related endpoints"""
        # Get due cards
        success1, response1 = self.run_test(
            "Get Due Cards for Study",
            "GET",
            "study/due?limit=10",
            200
        )
        
        # Get new cards
        success2, response2 = self.run_test(
            "Get New Cards for Study",
            "GET",
            "study/new?limit=5",
            200
        )
        
        # Test study response if we have cards
        if self.created_cards:
            study_response = {
                "card_id": self.created_cards[0],
                "quality": 4  # Good response
            }
            
            success3, response3 = self.run_test(
                "Record Study Response",
                "POST",
                "study/response",
                200,
                data=study_response
            )
            
            return success1 and success2 and success3
        
        return success1 and success2

    def test_study_session(self):
        """Test study session creation"""
        session_data = {
            "cards_studied": 2,
            "correct_answers": 1,
            "session_duration": 5,
            "study_mode": "flashcards"
        }
        
        success, response = self.run_test(
            "Create Study Session",
            "POST",
            "study/session",
            200,
            data=session_data
        )
        
        return success

    def test_progress_endpoints(self):
        """Test progress and statistics endpoints"""
        # Get statistics
        success1, response1 = self.run_test(
            "Get Progress Statistics",
            "GET",
            "progress/stats",
            200
        )
        
        # Get daily progress
        success2, response2 = self.run_test(
            "Get Daily Progress",
            "GET",
            "progress/daily?days=7",
            200
        )
        
        return success1 and success2

    def test_csv_import(self):
        """Test CSV import functionality"""
        # Create a test CSV content
        csv_content = """Word,Translation,Example,Notes,Difficulty
au revoir,goodbye,"Au revoir, à bientôt!",Farewell greeting,easy
difficile,difficult,Cette tâche est très difficile,Adjective describing complexity,medium
magnifique,magnificent,Le coucher de soleil est magnifique,Adjective for beauty,hard"""
        
        # Create a file-like object
        csv_file = io.StringIO(csv_content)
        files = {'file': ('test_vocabulary.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "Import CSV Vocabulary",
            "POST",
            "vocabulary/import?language=french",
            200,
            files=files
        )
        
        return success

    def test_update_and_delete(self):
        """Test update and delete operations"""
        if not self.created_cards:
            print("⚠️  Skipping update/delete tests - no cards created")
            return True
        
        card_id = self.created_cards[0]
        
        # Test update
        update_data = {
            "notes": "Updated notes for testing",
            "difficulty": "hard"
        }
        
        success1, response1 = self.run_test(
            "Update Vocabulary Card",
            "PUT",
            f"vocabulary/{card_id}",
            200,
            data=update_data
        )
        
        # Test delete
        success2, response2 = self.run_test(
            "Delete Vocabulary Card",
            "DELETE",
            f"vocabulary/{card_id}",
            200
        )
        
        if success2:
            self.created_cards.remove(card_id)
        
        return success1 and success2

    def cleanup_created_cards(self):
        """Clean up any remaining test cards"""
        print(f"\n🧹 Cleaning up {len(self.created_cards)} remaining test cards...")
        for card_id in self.created_cards[:]:
            try:
                url = f"{self.api_url}/vocabulary/{card_id}"
                response = requests.delete(url)
                if response.status_code == 200:
                    print(f"   ✅ Deleted card {card_id}")
                    self.created_cards.remove(card_id)
                else:
                    print(f"   ⚠️  Failed to delete card {card_id}")
            except Exception as e:
                print(f"   ❌ Error deleting card {card_id}: {e}")

def main():
    print("🚀 Starting Language Learning App API Tests")
    print("=" * 60)
    
    tester = LanguageLearningAPITester()
    
    try:
        # Run all tests
        tests = [
            ("Root Endpoint", tester.test_root_endpoint),
            ("Vocabulary Creation", tester.test_create_vocabulary_card),
            ("Vocabulary Retrieval", tester.test_get_vocabulary_cards),
            ("Study Endpoints", tester.test_study_endpoints),
            ("Study Session", tester.test_study_session),
            ("Progress Endpoints", tester.test_progress_endpoints),
            ("CSV Import", tester.test_csv_import),
            ("Update & Delete", tester.test_update_and_delete),
        ]
        
        for test_name, test_func in tests:
            print(f"\n📋 Running {test_name} Tests...")
            print("-" * 40)
            test_func()
            time.sleep(0.5)  # Small delay between test groups
        
    finally:
        # Always cleanup
        tester.cleanup_created_cards()
    
    # Print final results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())