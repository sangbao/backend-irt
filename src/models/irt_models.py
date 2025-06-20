from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Exam(db.Model):
    """Model cho đề thi"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Mã đề thi
    name = db.Column(db.String(200), nullable=False)  # Tên đề thi
    total_questions = db.Column(db.Integer, default=100)  # Tổng số câu
    part_division = db.Column(db.String(20), default='40-20-40')  # Cách chia phần
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    questions = db.relationship('Question', backref='exam', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='exam', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'total_questions': self.total_questions,
            'part_division': self.part_division,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'questions_count': len(self.questions),
            'submissions_count': len(self.submissions)
        }

class Question(db.Model):
    """Model cho câu hỏi"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)  # Số thứ tự câu (1-100)
    question_type = db.Column(db.String(50), nullable=False)  # Loại câu hỏi
    correct_answer = db.Column(db.Text, nullable=False)  # Đáp án đúng
    b_parameter = db.Column(db.Float, default=0.0)  # Tham số b_i trong IRT
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    statistics = db.relationship('QuestionStatistic', backref='question', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'exam_id': self.exam_id,
            'question_number': self.question_number,
            'question_type': self.question_type,
            'correct_answer': self.correct_answer,
            'b_parameter': self.b_parameter,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Submission(db.Model):
    """Model cho bài nộp của học sinh"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_name = db.Column(db.String(200), nullable=False)  # Tên học sinh
    student_code = db.Column(db.String(50), nullable=False)  # Mã học sinh
    answers = db.Column(db.Text, nullable=False)  # Đáp án (JSON string)
    
    # Kết quả IRT
    theta_part1 = db.Column(db.Float)  # θ phần 1
    theta_part2 = db.Column(db.Float)  # θ phần 2
    theta_part3 = db.Column(db.Float)  # θ phần 3
    theta_total = db.Column(db.Float)  # θ tổng
    
    # Điểm số
    score_part1 = db.Column(db.Float)  # Điểm phần 1
    score_part2 = db.Column(db.Float)  # Điểm phần 2
    score_part3 = db.Column(db.Float)  # Điểm phần 3
    total_score = db.Column(db.Float)  # Điểm tổng
    
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'exam_id': self.exam_id,
            'student_name': self.student_name,
            'student_code': self.student_code,
            'answers': json.loads(self.answers) if self.answers else [],
            'theta_part1': self.theta_part1,
            'theta_part2': self.theta_part2,
            'theta_part3': self.theta_part3,
            'theta_total': self.theta_total,
            'score_part1': self.score_part1,
            'score_part2': self.score_part2,
            'score_part3': self.score_part3,
            'total_score': self.total_score,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None
        }

class QuestionStatistic(db.Model):
    """Model cho thống kê câu hỏi"""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    total_attempts = db.Column(db.Integer, default=0)  # Tổng số lần làm
    correct_attempts = db.Column(db.Integer, default=0)  # Số lần làm đúng
    
    # Thống kê lựa chọn đáp án (cho trắc nghiệm)
    option_a_count = db.Column(db.Integer, default=0)
    option_b_count = db.Column(db.Integer, default=0)
    option_c_count = db.Column(db.Integer, default=0)
    option_d_count = db.Column(db.Integer, default=0)
    
    average_theta = db.Column(db.Float, default=0.0)  # θ trung bình của HS làm đúng
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'total_attempts': self.total_attempts,
            'correct_attempts': self.correct_attempts,
            'correct_rate': (self.correct_attempts / self.total_attempts * 100) if self.total_attempts > 0 else 0,
            'option_a_count': self.option_a_count,
            'option_b_count': self.option_b_count,
            'option_c_count': self.option_c_count,
            'option_d_count': self.option_d_count,
            'average_theta': self.average_theta,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

