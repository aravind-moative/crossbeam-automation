#!/usr/bin/env python3
"""
Test script to verify suggestion caching with 2-second delays
"""

import requests
import json
import time

def test_suggestion_caching():
    """Test that all suggestion questions are cached with 2-second delays"""
    
    # All suggestion questions
    suggestions = [
        'Show me high-priority opportunities',
        'Which partners have the most deals?',
        'Which opportunities to consider for a quick deal close?',
        'How are opportunities distributed across relationship statuses?'
    ]
    
    print("🧪 Testing Suggestion Caching with 2-Second Delays")
    print("=" * 60)
    
    for i, question in enumerate(suggestions, 1):
        print(f"\n📝 Test {i}: {question}")
        
        # First request (should be slow, no cache)
        print("   🔄 First request (should be slow)...")
        start_time = time.time()
        
        try:
            response = requests.post(
                'http://localhost:8000/api/chatbot-query',
                headers={'Content-Type': 'application/json'},
                json={'question': question}
            )
            
            if response.status_code == 200:
                first_duration = time.time() - start_time
                result = response.json()
                print(f"   ✅ First request completed in {first_duration:.2f}s")
                print(f"   📊 Results: {result.get('count', 0)} items")
                print(f"   📈 Visualization: {result.get('visualization_config', {}).get('type', 'unknown')}")
            else:
                print(f"   ❌ First request failed: {response.status_code}")
                continue
                
        except Exception as e:
            print(f"   ❌ First request error: {e}")
            continue
        
        # Second request (should be fast, cached with 2s delay)
        print("   🔄 Second request (should be cached with 2s delay)...")
        start_time = time.time()
        
        try:
            response = requests.post(
                'http://localhost:8000/api/chatbot-query',
                headers={'Content-Type': 'application/json'},
                json={'question': question}
            )
            
            if response.status_code == 200:
                second_duration = time.time() - start_time
                result = response.json()
                print(f"   ✅ Second request completed in {second_duration:.2f}s")
                print(f"   📊 Results: {result.get('count', 0)} items")
                print(f"   📈 Visualization: {result.get('visualization_config', {}).get('type', 'unknown')}")
                
                # Verify 2-second delay
                if 1.8 <= second_duration <= 2.5:  # Allow some tolerance
                    print("   🎯 2-second delay working correctly!")
                else:
                    print(f"   ⚠️  Expected ~2s delay, got {second_duration:.2f}s")
                    
            else:
                print(f"   ❌ Second request failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Second request error: {e}")
    
    # Check cache status
    print(f"\n📋 Cache Status:")
    try:
        response = requests.get('http://localhost:8000/api/cache-status')
        if response.status_code == 200:
            cache_info = response.json()
            print(f"   📦 Total cached queries: {cache_info.get('total_cached_queries', 0)}")
            print(f"   ⏱️  Cache duration: {cache_info.get('cache_duration_seconds', 0)}s")
            print(f"   📝 Cached queries: {cache_info.get('cached_queries', [])}")
        else:
            print(f"   ❌ Failed to get cache status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Cache status error: {e}")
    
    print("\n✅ Suggestion caching test completed!")

if __name__ == "__main__":
    test_suggestion_caching() 