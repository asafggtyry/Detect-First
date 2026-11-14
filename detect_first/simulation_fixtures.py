"""Synthetic-only messages for the randomized local demo; never used for training."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageFixture:
    scenario_label: str
    sender_name: str
    sender: str
    message: str
    saved_contact: bool


SIMULATION_FIXTURES = (
    MessageFixture("family_friend", "Mom", "mom", "Did you get home okay?", True),
    MessageFixture("family_friend", "Dad", "dad", "I left the spare key on the kitchen table.", True),
    MessageFixture("family_friend", "Aunt Maya", "aunt-maya", "Are we still meeting for lunch on Sunday?", True),
    MessageFixture("family_friend", "Leo", "leo", "I found your blue water bottle in my car.", True),
    MessageFixture("family_friend", "Nina", "nina", "The movie starts at 7:30. Want me to save you a seat?", True),
    MessageFixture("family_friend", "Grandpa", "grandpa", "The garden tomatoes are ready if you want some.", True),
    MessageFixture("family_friend", "Sam", "sam", "Thanks for sending those photos from the hike!", True),
    MessageFixture("family_friend", "Cousin Eva", "cousin-eva", "I will bring the board game tonight.", True),
    MessageFixture("family_friend", "Rosa", "rosa", "Your book is still here; I can drop it off tomorrow.", True),
    MessageFixture("family_friend", "Uncle Ben", "uncle-ben", "The train gets in around noon. See you there.", True),
    MessageFixture("normal_stranger", "Unknown - (202) 555-0142", "+12025550142", "Hi, I think you left your umbrella in the study room.", False),
    MessageFixture("normal_stranger", "Unknown - (415) 555-0173", "+14155550173", "Hello, is this the person who posted the desk for sale?", False),
    MessageFixture("normal_stranger", "Unknown - (312) 555-0118", "+13125550118", "Your library card was found near the north entrance.", False),
    MessageFixture("normal_stranger", "Unknown - (617) 555-0191", "+16175550191", "Hi! We are in the same evening ceramics class, right?", False),
    MessageFixture("normal_stranger", "Unknown - (206) 555-0136", "+12065550136", "I got your number from the volunteer signup sheet. Is Saturday still on?", False),
    MessageFixture("normal_stranger", "Unknown - (303) 555-0164", "+13035550164", "The package for apartment 4B was left with me by mistake.", False),
    MessageFixture("normal_stranger", "Unknown - (718) 555-0127", "+17185550127", "Hey, do you know whether the campus cafe is open today?", False),
    MessageFixture("normal_stranger", "Unknown - (503) 555-0185", "+15035550185", "I found a set of keys by the east parking lot. Are they yours?", False),
    MessageFixture("normal_stranger", "Unknown - (919) 555-0159", "+19195550159", "Hi, this is Jordan from the neighborhood clean-up group.", False),
    MessageFixture("normal_stranger", "Unknown - (702) 555-0108", "+17025550108", "Could you confirm the pickup time for the used bookshelf?", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (646) 555-0130", "+16465550130", "Hi, I'm a recruiter at Northstar Talent. Are you open to hearing about part-time remote openings?", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (213) 555-0181", "+12135550181", "🙂 We are hiring for a flexible assistant role. Pay a $35 onboarding fee today to reserve your interview.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (404) 555-0167", "+14045550167", "A remote data-entry position is available. Earn $450 per day and reply now to get started.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (512) 555-0124", "+15125550124", "Your profile was selected for a coordinator job. Send a $20 equipment deposit within 24 hours.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (801) 555-0196", "+18015550196", "Hello, we have a work opportunity from home. Purchase a training package before your first shift.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (917) 555-0149", "+19175550149", "We are recruiting campus ambassadors. Act now to secure your position; the schedule is flexible.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (614) 555-0178", "+16145550178", "A customer support opening is available with pay up to $300 daily. Reply today for the details.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (858) 555-0113", "+18585550113", "I can arrange a remote analyst interview this week. There is no charge to apply; let me know if interested.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (470) 555-0152", "+14705550152", "We have a delivery position for weekends. Please send a $45 activation payment to receive the starter kit.", False),
    MessageFixture("potential_fraudulent_recruiter", "Unknown - (971) 555-0106", "+19715550106", "Your application is moving forward. Reply immediately to confirm a short call about the role.", False),
)

SCENARIO_LABELS = (
    "family_friend",
    "normal_stranger",
    "potential_fraudulent_recruiter",
)

if any(sum(item.scenario_label == label for item in SIMULATION_FIXTURES) < 10
       for label in SCENARIO_LABELS):
    raise RuntimeError("Each synthetic demo scenario needs at least ten fixtures.")
