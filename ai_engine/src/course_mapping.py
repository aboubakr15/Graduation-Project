"""
Mapping of folder names to official course codes.
Add any missing folders and their corresponding codes here.
"""

COURSE_MAP = {
    # General / Year folders
    "year1": None, # Will be processed recursively
    "year2": None,
    "year3": None,
    "year4": None,
    
    # Common Course Folders -> Codes (from Student Guide PDF)
    "AI": "AI 310",
    "Advanced Machine Learning": "AI 370",
    "Algorithms": "CS 316",
    "Big Data": "IS 365",
    "Convex optimization": "AI 320",
    "Data Science": "IS 360",
    "Data Structure": "CS 214",
    "Database-1": "IS 211",
    "Deep Learning": "AI 335",
    "Ethics": "HU 334",
    "Human Rights": "HU 313",
    "Image Processing": "IT 441",
    "Logic Design": "CS 221",
    "Machine Learning": "AI 330",
    "Math-1": "MA 111",
    "Natural Language Processing": "AI 360",
    "Operation research": "IS 240",
    "PL1": "CS 112", # Programming 1
    "PL3": "CS 213", # Programming 2
    "Software": "CS 251", # Software Engineering 1
    "network": "IT 222", # Computer Networks 1
    "parallel processing": "CS 471",
    "probability and statistics 1": "ST 121",
    "probability and statistics 2": "ST 122",
    "Data Base 2": "IS 312",
    "economics": "HU 121",
    "evolutionary algorithms": "AI 420",
    "computational intelligence": "AI 430",
    "Software Engineering": "CS 251",
    "Database Systems": "IS 211",
    
    # Dept folders (if any chunks exist directly there)
    "CS": None,
    "IS": None,
    "IT": None,
}

def get_course_code(folder_name):
    """Returns the code for a given folder name, or the folder name itself if no mapping exists."""
    return COURSE_MAP.get(folder_name, folder_name)
