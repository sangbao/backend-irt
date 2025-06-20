from flask import Blueprint, request, jsonify
from src.models.irt_models import db, Exam, Question, Submission, QuestionStatistic
from src.services.irt_service import IRTProcessor
import numpy as np

irt_bp = Blueprint('irt', __name__)
irt_processor = IRTProcessor()

@irt_bp.route('/exams', methods=['GET'])
def get_exams():
    """Lấy danh sách đề thi"""
    try:
        exams = Exam.query.all()
        return jsonify({
            'success': True,
            'data': [exam.to_dict() for exam in exams]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@irt_bp.route('/exams', methods=['POST'])
def create_exam():
    """Tạo đề thi mới"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('code') or not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Thiếu mã đề hoặc tên đề'
            }), 400
        
        # Check if exam code already exists
        existing_exam = Exam.query.filter_by(code=data['code']).first()
        if existing_exam:
            return jsonify({
                'success': False,
                'error': 'Mã đề đã tồn tại'
            }), 400
        
        # Create exam
        exam = Exam(
            code=data['code'],
            name=data['name'],
            total_questions=data.get('totalQuestions', 100),
            part_division=data.get('partDivision', '40-20-40')
        )
        
        db.session.add(exam)
        db.session.flush()  # Get exam.id
        
        # Create questions
        questions_data = data.get('questions', [])
        for q_data in questions_data:
            question = Question(
                exam_id=exam.id,
                question_number=q_data.get('id', 1),
                question_type=q_data.get('type', 'multiple_choice'),
                correct_answer=q_data.get('correctAnswer', ''),
                b_parameter=q_data.get('bParameter', 0.0)
            )
            db.session.add(question)
            
            # Create initial statistics
            stat = QuestionStatistic(question_id=question.id)
            db.session.add(stat)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': exam.to_dict(),
            'message': 'Đề thi đã được tạo thành công'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@irt_bp.route('/exams/<exam_code>', methods=['GET'])
def get_exam(exam_code):
    """Lấy thông tin đề thi theo mã"""
    try:
        exam = Exam.query.filter_by(code=exam_code).first()
        if not exam:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy đề thi'
            }), 404
        
        # Get questions
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.question_number).all()
        
        exam_data = exam.to_dict()
        exam_data['questions'] = [q.to_dict() for q in questions]
        
        return jsonify({
            'success': True,
            'data': exam_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@irt_bp.route('/submissions', methods=['POST'])
def submit_answers():
    """Nộp bài thi"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['studentName', 'studentCode', 'examCode', 'answers']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Thiếu trường {field}'
                }), 400
        
        # Find exam
        exam = Exam.query.filter_by(code=data['examCode']).first()
        if not exam:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy đề thi'
            }), 404
        
        # Get questions
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.question_number).all()
        if len(questions) != 100:
            return jsonify({
                'success': False,
                'error': 'Đề thi chưa đủ 100 câu hỏi'
            }), 400
        
        # Process answers with IRT
        result = irt_processor.process_submission(data['answers'], questions)
        
        # Create submission record
        submission = Submission(
            exam_id=exam.id,
            student_name=data['studentName'],
            student_code=data['studentCode'],
            answers=json.dumps(result['parsed_answers']),
            theta_part1=result['theta_part1'],
            theta_part2=result['theta_part2'],
            theta_part3=result['theta_part3'],
            theta_total=result['theta_total'],
            score_part1=result['score_part1'],
            score_part2=result['score_part2'],
            score_part3=result['score_part3'],
            total_score=result['total_score']
        )
        
        db.session.add(submission)
        
        # Update question statistics
        for i, question in enumerate(questions):
            stat = QuestionStatistic.query.filter_by(question_id=question.id).first()
            if not stat:
                stat = QuestionStatistic(question_id=question.id)
                db.session.add(stat)
            
            # Update counts
            stat.total_attempts += 1
            if result['responses'][i] == 1:
                stat.correct_attempts += 1
            
            # Update option counts for multiple choice
            if question.question_type == 'multiple_choice':
                student_answer = result['parsed_answers'].get(question.question_number, '').upper()
                if student_answer == 'A':
                    stat.option_a_count += 1
                elif student_answer == 'B':
                    stat.option_b_count += 1
                elif student_answer == 'C':
                    stat.option_c_count += 1
                elif student_answer == 'D':
                    stat.option_d_count += 1
        
        db.session.commit()
        
        # Update b_parameters (after commit to get all submissions)
        update_b_parameters(exam.id)
        
        return jsonify({
            'success': True,
            'data': submission.to_dict(),
            'message': 'Bài thi đã được nộp thành công'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@irt_bp.route('/submissions/<student_code>/<exam_code>', methods=['GET'])
def get_submission_result(student_code, exam_code):
    """Lấy kết quả bài thi của học sinh"""
    try:
        # Find exam
        exam = Exam.query.filter_by(code=exam_code).first()
        if not exam:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy đề thi'
            }), 404
        
        # Find submission
        submission = Submission.query.filter_by(
            exam_id=exam.id,
            student_code=student_code
        ).first()
        
        if not submission:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy bài thi'
            }), 404
        
        # Get questions for detailed results
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.question_number).all()
        
        # Calculate detailed results
        parsed_answers = json.loads(submission.answers)
        question_details = []
        
        for question in questions:
            student_answer = parsed_answers.get(str(question.question_number), '')
            is_correct = irt_processor.check_answer(
                student_answer, 
                question.correct_answer, 
                question.question_type
            )
            
            # Determine part
            part = 1 if question.question_number <= 40 else (2 if question.question_number <= 60 else 3)
            
            question_details.append({
                'questionNumber': question.question_number,
                'studentAnswer': student_answer,
                'correctAnswer': question.correct_answer,
                'isCorrect': is_correct,
                'part': part,
                'irtScore': question.b_parameter  # Simplified IRT score
            })
        
        # Calculate ranking
        all_submissions = Submission.query.filter_by(exam_id=exam.id).all()
        sorted_submissions = sorted(all_submissions, key=lambda x: x.total_score or 0, reverse=True)
        
        position = 1
        for i, sub in enumerate(sorted_submissions):
            if sub.id == submission.id:
                position = i + 1
                break
        
        percentile = int((len(sorted_submissions) - position + 1) / len(sorted_submissions) * 100)
        
        result_data = submission.to_dict()
        result_data.update({
            'examInfo': {
                'code': exam.code,
                'name': exam.name
            },
            'questionDetails': question_details,
            'ranking': {
                'position': position,
                'totalStudents': len(sorted_submissions),
                'percentile': percentile
            }
        })
        
        return jsonify({
            'success': True,
            'data': result_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@irt_bp.route('/statistics/<exam_code>', methods=['GET'])
def get_exam_statistics(exam_code):
    """Lấy thống kê đề thi"""
    try:
        # Find exam
        exam = Exam.query.filter_by(code=exam_code).first()
        if not exam:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy đề thi'
            }), 404
        
        # Get questions and statistics
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.question_number).all()
        submissions = Submission.query.filter_by(exam_id=exam.id).all()
        
        # Overall statistics
        total_students = len(submissions)
        avg_score = sum(s.total_score or 0 for s in submissions) / total_students if total_students > 0 else 0
        avg_theta = sum(s.theta_total or 0 for s in submissions) / total_students if total_students > 0 else 0
        
        # Question statistics
        question_stats = []
        for question in questions:
            stat = QuestionStatistic.query.filter_by(question_id=question.id).first()
            if stat:
                question_data = question.to_dict()
                question_data['statistics'] = stat.to_dict()
                question_stats.append(question_data)
        
        # Theta distribution for histogram
        theta_values = [s.theta_total for s in submissions if s.theta_total is not None]
        theta_distribution = []
        
        if theta_values:
            # Create histogram bins
            bins = np.linspace(-3, 3, 21)  # 20 bins
            hist, bin_edges = np.histogram(theta_values, bins=bins)
            
            for i in range(len(hist)):
                theta_distribution.append({
                    'theta': round((bin_edges[i] + bin_edges[i+1]) / 2, 1),
                    'count': int(hist[i])
                })
        
        # Part scores
        part_scores = []
        if total_students > 0:
            part_scores = [
                {
                    'part': 'Phần 1 (1-40)',
                    'avgScore': sum(s.score_part1 or 0 for s in submissions) / total_students,
                    'count': total_students
                },
                {
                    'part': 'Phần 2 (41-60)',
                    'avgScore': sum(s.score_part2 or 0 for s in submissions) / total_students,
                    'count': total_students
                },
                {
                    'part': 'Phần 3 (61-100)',
                    'avgScore': sum(s.score_part3 or 0 for s in submissions) / total_students,
                    'count': total_students
                }
            ]
        
        return jsonify({
            'success': True,
            'data': {
                'exam': exam.to_dict(),
                'overview': {
                    'totalStudents': total_students,
                    'avgScore': round(avg_score, 1),
                    'avgTheta': round(avg_theta, 2),
                    'reliability': 0.85  # Mock Cronbach's Alpha
                },
                'questionStats': question_stats,
                'thetaDistribution': theta_distribution,
                'partScores': part_scores
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def update_b_parameters(exam_id):
    """Cập nhật tham số b_i cho tất cả câu hỏi trong đề thi"""
    try:
        questions = Question.query.filter_by(exam_id=exam_id).all()
        submissions = Submission.query.filter_by(exam_id=exam_id).all()
        
        if len(submissions) < 5:  # Cần ít nhất 5 học sinh
            return
        
        for question in questions:
            # Lấy responses và thetas cho câu này
            question_responses = []
            student_thetas = []
            
            for submission in submissions:
                parsed_answers = json.loads(submission.answers)
                student_answer = parsed_answers.get(str(question.question_number), '')
                
                is_correct = irt_processor.check_answer(
                    student_answer,
                    question.correct_answer,
                    question.question_type
                )
                
                question_responses.append(1 if is_correct else 0)
                student_thetas.append(submission.theta_total or 0)
            
            # Cập nhật b_parameter
            new_b = irt_processor.update_b_parameter(question_responses, student_thetas)
            question.b_parameter = new_b
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error updating b_parameters: {e}")
        db.session.rollback()

